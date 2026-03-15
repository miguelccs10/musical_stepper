#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de Teste - Motor 0
-------------------------
Testa a fiação e o funcionamento do Motor 0 (Melodia) tocando uma escala musical.

Execução:
    sudo pigpiod
    python3 test_motor.py
"""

import time
import pigpio
import sys

# ==========================================
# CONFIGURAÇÃO DOS PINOS (MOTOR 0)
# ==========================================
STEP_PIN = 17
DIR_PIN = 27
ENABLE_PIN = 18

print("Conectando ao daemon do pigpio...")
pi = pigpio.pi()

if not pi.connected:
    print("Erro: Não foi possível conectar ao daemon do pigpio.")
    print("Execute 'sudo pigpiod' no terminal antes de rodar o script.")
    sys.exit(1)

# Configuração dos pinos como saída
pi.set_mode(ENABLE_PIN, pigpio.OUTPUT)
pi.set_mode(STEP_PIN, pigpio.OUTPUT)
pi.set_mode(DIR_PIN, pigpio.OUTPUT)

# Habilita o driver (TMC2209 Enable é ativo em LOW)
print("Habilitando driver TMC2209...")
pi.write(ENABLE_PIN, 0)

# Frequências da escala de Dó Maior (C4 a C5) em Hz
escala_do_maior = [261, 293, 329, 349, 392, 440, 493, 523]

try:
    print("\nTocando escala musical (Subindo)...")
    pi.write(DIR_PIN, 0) # Define direção 1
    
    for freq in escala_do_maior:
        print(f"Frequência: {freq} Hz")
        # Inicia o PWM na frequência da nota com 50% de duty cycle (128 de 255)
        pi.set_PWM_frequency(STEP_PIN, freq)
        pi.set_PWM_dutycycle(STEP_PIN, 128)
        time.sleep(0.5) # Toca a nota por meio segundo
        
    print("\nPausa...")
    pi.set_PWM_dutycycle(STEP_PIN, 0) # Para o motor
    time.sleep(0.5)
    
    print("\nTocando escala musical (Descendo e invertendo direção)...")
    pi.write(DIR_PIN, 1) # Define direção 2
    
    for freq in reversed(escala_do_maior):
        print(f"Frequência: {freq} Hz")
        pi.set_PWM_frequency(STEP_PIN, freq)
        pi.set_PWM_dutycycle(STEP_PIN, 128)
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nTeste interrompido pelo usuário.")
finally:
    print("\nDesligando motor e driver...")
    pi.set_PWM_dutycycle(STEP_PIN, 0) # Para os pulsos
    pi.write(ENABLE_PIN, 1)           # Desabilita o driver (HIGH)
    pi.stop()                         # Fecha conexão com pigpio
    print("Teste finalizado com sucesso.")
