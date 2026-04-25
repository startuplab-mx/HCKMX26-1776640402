import socket
import time

def send_syslog(message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message.encode(), ("127.0.0.1", 5140))
    time.sleep(0.5)

print("Enviando tráfico de prueba al analizador ZKTCA...")

# 1. Prueba de Grooming (Juego -> Chat en poco tiempo)
print("\n--- Simulando patrón de Grooming ---")
# Juega Minecraft (Puerto 19132)
send_syslog("ZKTCA_METADATA: src_ip=192.168.1.100 dst_ip=8.8.8.8 src_port=50000 dst_port=19132 protocol=17 packets=100 bytes=5000 event=NEW")
time.sleep(1)
# Cambia a Telegram/Discord (Puerto 443) rápidamente
send_syslog("ZKTCA_METADATA: src_ip=192.168.1.100 dst_ip=104.16.12.1 src_port=50001 dst_port=443 protocol=6 packets=20 bytes=1500 event=NEW")

# 2. Prueba de Bullying (Picos asimétricos entrantes)
print("\n--- Simulando patrón de Bullying/Acoso ---")
# Múltiples IPs externas enviando paquetes a la IP del niño (192.168.1.100)
send_syslog("ZKTCA_METADATA: src_ip=200.1.1.1 dst_ip=192.168.1.100 src_port=443 dst_port=55000 protocol=6 packets=50 bytes=20000 event=NEW")
send_syslog("ZKTCA_METADATA: src_ip=200.1.1.2 dst_ip=192.168.1.100 src_port=443 dst_port=55001 protocol=6 packets=50 bytes=20000 event=NEW")
send_syslog("ZKTCA_METADATA: src_ip=200.1.1.3 dst_ip=192.168.1.100 src_port=443 dst_port=55002 protocol=6 packets=50 bytes=20000 event=NEW")
send_syslog("ZKTCA_METADATA: src_ip=200.1.1.4 dst_ip=192.168.1.100 src_port=443 dst_port=55003 protocol=6 packets=50 bytes=20000 event=NEW")

# 3. Prueba de Actividad Nocturna
print("\n--- Simulando patrón de Uso Nocturno ---")
# Enviamos un evento DESTROY con muchos bytes para que el analizador calcule una duración alta
# Nota: La función 'check_night_activity' verifica el datetime de la máquina.
# Para forzar esto podríamos falsear la hora, pero el script usa time.time()
# Vamos a enviar simplemente el paquete. Si es de día, no saltará la alerta,
# pero al menos vemos que se procesa sin error.
send_syslog("ZKTCA_METADATA: src_ip=192.168.1.100 dst_ip=1.1.1.1 src_port=52000 dst_port=443 protocol=6 packets=10000 bytes=50000000 event=DESTROY")

print("\nPruebas enviadas. Revisa la consola donde corre analyzer.py.")
