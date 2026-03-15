#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Musical Stepper Maestro (RP3 + TMC2209)
---------------------------------------
Converte arquivos MIDI em sinais de frequência para 3 motores de passo NEMA 17.
Cada motor representa uma trilha/canal diferente da melodia.

Dependências:
    pip3 install mido pigpio

Execução:
    sudo pigpiod  # Inicia o daemon do pigpio
    python3 maestro.py <arquivo_midi.mid>
"""

import sys
import time
import math
import mido
import pigpio

# ==========================================
# CONFIGURAÇÃO DE HARDWARE
# ==========================================

# Pino ENABLE unificado para todos os drivers TMC2209
ENABLE_PIN = 18

# Configuração dos Motores: { ID: {'step': GPIO, 'dir': GPIO} }
MOTORS = {
    0: {'step': 17, 'dir': 27}, # Motor 1 (Melodia Principal)
    1: {'step': 22, 'dir': 23}, # Motor 2 (Harmonia)
    2: {'step': 24, 'dir': 25}  # Motor 3 (Baixo)
}

# ==========================================
# INICIALIZAÇÃO DO PIGPIO
# ==========================================

pi = pigpio.pi()
if not pi.connected:
    print("Erro: Não foi possível conectar ao daemon do pigpio.")
    print("Execute 'sudo pigpiod' no terminal antes de rodar o script.")
    sys.exit(1)

# Configura os pinos como saída
pi.set_mode(ENABLE_PIN, pigpio.OUTPUT)
# Habilita os drivers (TMC2209 Enable é ativo em LOW)
pi.write(ENABLE_PIN, 0)

for m_id, pins in MOTORS.items():
    pi.set_mode(pins['step'], pigpio.OUTPUT)
    pi.set_mode(pins['dir'], pigpio.OUTPUT)
    pi.write(pins['step'], 0)
    pi.write(pins['dir'], 0)

# ==========================================
# FUNÇÕES DE CONTROLE
# ==========================================

def midi_note_to_freq(note):
    """
    Converte nota MIDI para frequência em Hz.
    Fórmula: f = 440 * 2^((n-69)/12)
    """
    return int(round(440.0 * (2.0 ** ((note - 69.0) / 12.0))))

def play_tone(motor_id, freq):
    """
    Gera um sinal PWM no pino STEP do motor especificado.
    Utiliza DMA do pigpio para precisão sem bloquear a thread principal.
    """
    step_pin = MOTORS[motor_id]['step']
    if freq > 0:
        # Define a frequência do PWM (pigpio ajustará para a mais próxima suportada)
        pi.set_PWM_frequency(step_pin, freq)
        # Define o duty cycle para 50% (128 de 255) para onda quadrada perfeita
        pi.set_PWM_dutycycle(step_pin, 128)
    else:
        # Para o motor zerando o duty cycle
        pi.set_PWM_dutycycle(step_pin, 0)

def stop_all_motors():
    """Para todos os motores e desabilita os drivers."""
    for m_id in MOTORS:
        play_tone(m_id, 0)
    # Desabilita os drivers (HIGH)
    pi.write(ENABLE_PIN, 1)

# ==========================================
# PROCESSAMENTO MIDI
# ==========================================

def get_top_channels(mid, num_channels=3):
    """
    Analisa o arquivo MIDI e retorna os canais mais ativos
    (com mais mensagens de note_on).
    """
    channel_activity = {}
    
    for track in mid.tracks:
        for msg in track:
            if not msg.is_meta and msg.type == 'note_on' and msg.velocity > 0:
                ch = msg.channel
                # Ignora o canal 9 (geralmente percussão/bateria no padrão General MIDI)
                if ch == 9:
                    continue
                channel_activity[ch] = channel_activity.get(ch, 0) + 1
                
    # Ordena os canais por atividade (decrescente)
    sorted_channels = sorted(channel_activity.items(), key=lambda item: item[1], reverse=True)
    
    # Retorna apenas os IDs dos 'num_channels' mais ativos
    top_channels = [ch[0] for ch in sorted_channels[:num_channels]]
    
    # Se houver menos canais que motores, preenche com os disponíveis
    while len(top_channels) < num_channels and len(sorted_channels) > len(top_channels):
         top_channels.append(sorted_channels[len(top_channels)][0])
         
    return top_channels

def play_midi(file_path):
    """
    Lê o arquivo MIDI, mapeia os canais e envia os comandos de frequência
    para os motores em tempo real.
    """
    try:
        mid = mido.MidiFile(file_path)
    except Exception as e:
        print(f"Erro ao carregar o arquivo MIDI '{file_path}': {e}")
        return

    print(f"Arquivo carregado: {file_path}")
    print(f"Duração estimada: {mid.length:.2f} segundos")

    # Mapeia os 3 canais mais ativos para os 3 motores
    top_channels = get_top_channels(mid, 3)
    print(f"Canais MIDI mapeados para os motores: {top_channels}")
    
    # Dicionário para mapear canal MIDI -> ID do Motor
    channel_to_motor = {ch: i for i, ch in enumerate(top_channels)}
    
    # Estado atual das notas para evitar que um note_off desligue uma nota nova
    # motor_id -> nota_atual
    current_notes = {0: None, 1: None, 2: None}
    
    # Alterna a direção a cada nota para evitar que o motor ande infinitamente para um lado
    directions = {0: 0, 1: 0, 2: 0}

    print("\nIniciando 'Orquestra Mecânica'...")
    print("Pressione Ctrl+C para parar.\n")
    
    try:
        # mid.play() itera pelas mensagens respeitando o tempo (delay) entre elas.
        # Isso resolve o problema de concorrência e duração das notas automaticamente.
        for msg in mid.play():
            if msg.is_meta:
                continue
                
            if msg.type in ['note_on', 'note_off']:
                ch = msg.channel
                
                # Ignora canais que não foram mapeados
                if ch not in channel_to_motor:
                    continue
                    
                motor_id = channel_to_motor[ch]
                
                # Note ON
                if msg.type == 'note_on' and msg.velocity > 0:
                    freq = midi_note_to_freq(msg.note)
                    current_notes[motor_id] = msg.note
                    
                    # Alterna a direção
                    directions[motor_id] = 1 - directions[motor_id]
                    pi.write(MOTORS[motor_id]['dir'], directions[motor_id])
                    
                    play_tone(motor_id, freq)
                
                # Note OFF
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # Só desliga se a nota que está tocando for a mesma do note_off
                    if current_notes[motor_id] == msg.note:
                        play_tone(motor_id, 0)
                        current_notes[motor_id] = None

    except KeyboardInterrupt:
        print("\nReprodução interrompida pelo usuário.")
    finally:
        print("Desligando motores...")
        stop_all_motors()
        pi.stop()
        print("Finalizado.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 maestro.py <caminho_para_arquivo_midi.mid>")
        sys.exit(1)
        
    midi_file = sys.argv[1]
    play_midi(midi_file)
