/*
 * Xbox 360 Fat RF Module Sync & Power-Off Controller — ATtiny13A @ 1.2 MHz (default fuses)
 *
 * Unisce il meglio di agarmash/Xreceiver e MicroKnot:
 *  - Pinout identico alla basetta PET-G (agarmash):
 *      PB0 (pin 5) = CLOCK (RF pin 7)
 *      PB1 (pin 6) = SYNC  (RF pin 5, tasto centrale)
 *      PB2 (pin 7) = DATA  (RF pin 6)
 *  - Timing 10-bit migliorato per moduli Rev. H + rilascio linea DATA in alta impedenza
 *  - Animazione anello verde (Ring of Light) all'avvio e durante il Sync
 *  - Pressione breve (< 1 s): avvia Sync + animazione anello verde
 *  - Pressione lunga (>= 1 s): spegne tutti i controller collegati
 *
 * Compilazione (fuse di fabbrica ATtiny13A: 9.6 MHz / 8 = 1.2 MHz):
 *   avr-gcc -mmcu=attiny13a -Os -DF_CPU=1200000UL -o x360_rf_attiny13_v2.elf x360_rf_attiny13_v2.c
 *   avr-objcopy -O ihex -R .eeprom x360_rf_attiny13_v2.elf x360_rf_attiny13_v2.hex
 */
#ifndef F_CPU
#define F_CPU 1200000UL
#endif

#include <avr/io.h>
#include <util/delay.h>
#include <stdint.h>

#define CLOCK_PIN PB0   // ATtiny13A pin 5 -> RF pin 7
#define SYNC_PIN  PB1   // ATtiny13A pin 6 -> RF pin 5 (tasto centrale)
#define DATA_PIN  PB2   // ATtiny13A pin 7 -> RF pin 6

// Comandi a 10 bit (MSB first)
#define CMD_LED_INIT  0x084U  // 0010000100 - inizializza LED + LED centrale verde
#define CMD_LED_ANIM  0x085U  // 0010000101 - animazione rotante anello verde
#define CMD_SYNC      0x004U  // 0000000100 - avvia sincronizzazione controller
#define CMD_CTRL_OFF  0x009U  // 0000001001 - spegne tutti i controller connessi
#define CMD_RING_ON   0x0A9U  // 0010101001 - accende anello feedback
#define CMD_RING_RG   0x0B6U  // 0010110110 - rosso/verde feedback spegnimento
#define CMD_RING_OFF1 0x0A0U  // 0010100000 - spegne anello
#define CMD_RING_OFF2 0x0B0U  // 0010110000 - spegne anello

static uint8_t wait_clock_change(uint8_t prev) {
    uint16_t timeout = 40000;
    uint8_t cur;
    do {
        cur = (PINB >> CLOCK_PIN) & 1U;
        if (cur != prev) return cur;
    } while (--timeout);
    return cur;
}

static void send_cmd(uint16_t cmd10) {
    // Start: porta DATA LOW (output)
    DDRB |= (1U << DATA_PIN);
    PORTB &= ~(1U << DATA_PIN);
    _delay_us(5);

    uint8_t prev = (PINB >> CLOCK_PIN) & 1U;
    for (uint8_t i = 0; i < 10; i++) {
        prev = wait_clock_change(prev);
        _delay_us(5);

        if (cmd10 & (1U << (9 - i))) {
            PORTB |= (1U << DATA_PIN);
        } else {
            PORTB &= ~(1U << DATA_PIN);
        }

        _delay_us(10); // hold lungo per compatibilita' Rev. H
        prev = wait_clock_change(prev);
    }

    // Idle: rilascia DATA in alta impedenza con pull-up
    PORTB |= (1U << DATA_PIN);
    DDRB &= ~(1U << DATA_PIN);
}

static void init_leds(void) {
    send_cmd(CMD_LED_INIT);
    _delay_ms(50);
    send_cmd(CMD_LED_ANIM);
    _delay_ms(50);
}

int main(void) {
    // Ingressi con pull-up interni attivi (lavorano bene sia con che senza R2/R3 esterni)
    DDRB &= ~((1U << CLOCK_PIN) | (1U << SYNC_PIN) | (1U << DATA_PIN));
    PORTB |= (1U << CLOCK_PIN) | (1U << SYNC_PIN) | (1U << DATA_PIN);

    // Attesa avvio interno del modulo RF
    _delay_ms(2500);
    init_leds();

    for (;;) {
        if (!(PINB & (1U << SYNC_PIN))) {
            _delay_ms(30); // debounce
            if (!(PINB & (1U << SYNC_PIN))) {
                uint16_t held_ms = 0;
                uint8_t long_press = 0;

                while (!(PINB & (1U << SYNC_PIN))) {
                    _delay_ms(20);
                    held_ms += 20;
                    if (held_ms >= 1000) {
                        long_press = 1;
                        break;
                    }
                }

                if (!long_press) {
                    // Pressione breve: Sync + animazione rotante verde
                    send_cmd(CMD_SYNC);
                    for (uint8_t i = 0; i < 3; i++) {
                        _delay_ms(50);
                        send_cmd(CMD_LED_ANIM);
                    }
                    _delay_ms(1500);
                } else {
                    // Pressione lunga: spegne tutti i controller connessi
                    send_cmd(CMD_RING_ON);
                    _delay_ms(10);
                    send_cmd(CMD_RING_RG);
                    _delay_ms(10);
                    send_cmd(CMD_CTRL_OFF);
                    _delay_ms(500);
                    send_cmd(CMD_RING_OFF1);
                    _delay_ms(10);
                    send_cmd(CMD_RING_OFF2);
                    // Attendi rilascio tasto
                    while (!(PINB & (1U << SYNC_PIN))) {
                        _delay_ms(20);
                    }
                    _delay_ms(1000);
                }
            }
        }
    }
}
