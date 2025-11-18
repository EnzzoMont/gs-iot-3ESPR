import network
import time
from machine import Pin, I2C, ADC
from umqtt.simple import MQTTClient
import ujson

try:
    from i2c_lcd import I2cLcd
    has_lcd = True
except:
    has_lcd = False

# --- CONFIGURAÇÕES ---
MQTT_CLIENT_ID = "gs_iot_career_2025_esp32"
MQTT_BROKER    = "test.mosquitto.org"
MQTT_TOPIC_PUB = "fiap/gs2025/respostas"  
MQTT_TOPIC_SUB = "fiap/gs2025/controle"   

PERGUNTAS = [
    "1. Overfitting", "2. Vies Dados", "3. Modelo Lento", "4. Alucinacao LLM", "5. Python vs C++",
    "6. Conflito Time", "7. Prazo Estourado", "8. Colega Toxico", "9. Burnout Equipe", "10. Erro Critico",
    "11. Queda Vendas", "12. Grafico Pizza", "13. Dados Sujos", "14. Dash Lento", "15. Storytelling"
]

btn_a = Pin(12, Pin.IN, Pin.PULL_UP)
btn_b = Pin(14, Pin.IN, Pin.PULL_UP)
btn_c = Pin(27, Pin.IN, Pin.PULL_UP)
btn_d = Pin(13, Pin.IN, Pin.PULL_UP)
pot = ADC(Pin(34))
pot.atten(ADC.ATTN_11DB)

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=10000)
lcd = None
if has_lcd:
    try:
        lcd = I2cLcd(i2c, 0x27, 2, 16)
        lcd.clear()
    except: pass

# --- VARIÁVEIS DE CONTROLE ---
estado_sistema = "AGUARDANDO_LOGIN" 
nome_candidato = ""

def mqtt_callback(topic, msg):
    global estado_sistema, nome_candidato
    print(f"Mensagem recebida: {msg}")
    try:
        dados = ujson.loads(msg)
        if dados.get("acao") == "INICIAR_TESTE":
            nome_candidato = dados.get("nome", "Colaborador")
            print(f"Login recebido! Iniciando prova para: {nome_candidato}")
            client.publish(MQTT_TOPIC_PUB, ujson.dumps({
                "tipo": "NOVA_SESSAO", 
                "nome": nome_candidato,
                "matricula": dados.get("matricula", "--"),
                "area": dados.get("area", "--")
            }))
            
            estado_sistema = "RODANDO_PROVA"
    except:
        print("Erro ao decodificar JSON")

# --- CONEXÃO ---
print("Conectando WiFi...", end="")
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect('Wokwi-GUEST', '')
while not sta_if.isconnected(): time.sleep(0.1)
print(" OK!")

print("Conectando MQTT...", end="")
try:
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER)
    client.set_callback(mqtt_callback) 
    client.connect()
    client.subscribe(MQTT_TOPIC_SUB)   
    print(" OK! Aguardando Login...")
except:
    print(" Erro na conexão MQTT (Verifique Broker)")

def esperar_botoes_soltos():
    while btn_a.value() == 0 or btn_b.value() == 0 or btn_c.value() == 0 or btn_d.value() == 0:
        time.sleep(0.1)

# --- LOOP PRINCIPAL ---
while True:
    try:
        client.check_msg()
    except: pass

    if estado_sistema == "AGUARDANDO_LOGIN":
        if lcd:
            lcd.clear()
            lcd.putstr("AGUARDANDO LOGIN")
            lcd.move_to(0,1)
            lcd.putstr("NO COMPUTADOR...")
        time.sleep(1) 

    elif estado_sistema == "RODANDO_PROVA":
        if lcd:
            lcd.clear()
            lcd.putstr("Ola,")
            lcd.move_to(0,1)
            lcd.putstr(nome_candidato[:16]) 
        time.sleep(2)

        for questao in PERGUNTAS:
            esperar_botoes_soltos()
            msg = ujson.dumps({"tipo": "PERGUNTA_INICIO", "pergunta": questao})
            client.publish(MQTT_TOPIC_PUB, msg)
            
            if lcd:
                lcd.clear()
                lcd.putstr(questao)
                lcd.move_to(0,1)
                lcd.putstr("?: A B C D")
            
            inicio = time.ticks_ms()
            respondeu = False
            
            # Loop de resposta
            while True:
                client.check_msg() 
                agora = time.ticks_ms()
                delta = time.ticks_diff(agora, inicio)
                
                if delta > 30000: 
                    if lcd: lcd.clear(); lcd.putstr("TEMPO ESGOTADO"); time.sleep(1)
                    break

                if btn_a.value() == 0: resp="A"; respondeu=True; tempo=delta; break
                if btn_b.value() == 0: resp="B"; respondeu=True; tempo=delta; break
                if btn_c.value() == 0: resp="C"; respondeu=True; tempo=delta; break
                if btn_d.value() == 0: resp="D"; respondeu=True; tempo=delta; break
                time.sleep(0.05)

            if respondeu:
                stress = int((pot.read() / 4095) * 100)
                if lcd: lcd.clear(); lcd.putstr(f"Resp:{resp} Stress:{stress}%")
                msg_fim = ujson.dumps({
                    "tipo": "RESPOSTA",
                    "pergunta": questao,
                    "resposta": resp,
                    "tempo_ms": tempo,
                    "stress": stress,
                    "nome": nome_candidato
                })
                client.publish(MQTT_TOPIC_PUB, msg_fim)
                time.sleep(1)

        if lcd:
            lcd.clear()
            lcd.putstr("OBRIGADO!")
            lcd.move_to(0,1)
            lcd.putstr("FIM DA SESSAO")
        
        client.publish(MQTT_TOPIC_PUB, ujson.dumps({"tipo": "FIM_PROVA"}))
        
        time.sleep(3)
        estado_sistema = "AGUARDANDO_LOGIN" 