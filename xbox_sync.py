#!/usr/bin/env python3
"""
Xbox 360 RF Sync Script
Basato sulla libreria xbox_rf di Tino Goehlert

Collegamenti:
- GPIO 24 (pin fisico 18) → Xbox RF module pin 6 (DATA)
- GPIO 25 (pin fisico 22) → Xbox RF module pin 7 (CLOCK)
- GND → GND

Esegui con: sudo python3 xbox_sync.py
"""

import RPi.GPIO as GPIO
import time
import sys

# Configurazione pin (numeri BCM)
DATA_PIN = 24   # corrisponde a wiringPi pin 5
CLOCK_PIN = 25  # corrisponde a wiringPi pin 6

# Comandi (dalla libreria originale)
commands = {
    "led_cmd": "0010000100",      # Attiva LEDs
    "anim_cmd": "0010000101",     # Animazione startup
    "ctl_sync": "0000000100",     # ⭐ SYNC COMMAND ⭐
    "ctl_shutdown": "0000001001"  # Spegni controller
}

def setup_gpio():
    """Inizializza GPIO"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(DATA_PIN, GPIO.OUT)
    GPIO.setup(CLOCK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.output(DATA_PIN, GPIO.HIGH)  # Idle high
    print(f"GPIO configurati: DATA={DATA_PIN}, CLOCK={CLOCK_PIN}")

def send_command(command_bits):
    """
    Invia comando al modulo RF con sincronizzazione clock
    Replica esattamente la logica della libreria originale
    """
    print(f"Invio comando: {command_bits}")
    
    # Start: DATA low
    GPIO.output(DATA_PIN, GPIO.LOW)
    
    # Leggi stato iniziale clock
    prev_clock = GPIO.input(CLOCK_PIN)
    
    # Invia ogni bit sincronizzato con clock
    for i, bit_char in enumerate(command_bits):
        bit_value = int(bit_char)
        
        # Aspetta fronte di clock
        current_clock = GPIO.input(CLOCK_PIN)
        while current_clock == prev_clock:
            current_clock = GPIO.input(CLOCK_PIN)
        prev_clock = current_clock
        
        # Imposta bit dati
        GPIO.output(DATA_PIN, bit_value)
        print(f"Bit {i}: {bit_value}")
        
        # Aspetta prossimo fronte di clock
        current_clock = GPIO.input(CLOCK_PIN)
        while current_clock == prev_clock:
            current_clock = GPIO.input(CLOCK_PIN)
        prev_clock = current_clock
    
    # Fine trasmissione: DATA high
    GPIO.output(DATA_PIN, GPIO.HIGH)
    print("Comando inviato!")

def init_module():
    """Inizializza il modulo RF (come nella libreria originale)"""
    print("Inizializzazione modulo RF...")
    send_command(commands["led_cmd"])
    time.sleep(0.05)  # 50ms delay
    print("Modulo inizializzato!")

def sync_controller():
    """Avvia procedura di sync"""
    print("\n🎮 AVVIO SYNC CONTROLLER 🎮")
    print("=" * 40)
    
    # Inizializza modulo
    init_module()
    
    # Invia comando sync
    print("Invio comando sync...")
    send_command(commands["ctl_sync"])
    time.sleep(0.2)  # 200ms delay
    
    print("\n✅ COMANDO SYNC INVIATO!")
    print("🔥 PREMI IL TASTO SYNC SUL CONTROLLER ORA!")
    print("⏰ Hai circa 20 secondi...")
    
    # Countdown visivo
    for i in range(20, 0, -1):
        print(f"\r⏱️  Tempo rimanente: {i:2d} secondi", end="", flush=True)
        time.sleep(1)
    
    print("\n\n⚠️  Timeout sync scaduto.")

def cleanup():
    """Pulizia GPIO"""
    GPIO.cleanup()
    print("GPIO puliti.")

def main():
    try:
        print("Xbox 360 RF Controller Sync")
        print("=" * 30)
        
        # Verifica permessi
        if GPIO.RPI_REVISION is None:
            print("❌ ERRORE: Esegui come sudo!")
            sys.exit(1)
        
        setup_gpio()
        sync_controller()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Interrotto dall'utente")
    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
