# Xbox 360 RF Module Sync Manager

This Python script enables sync mode on a Xbox 360 FAT RF module using Raspberry Pi GPIO pins (Clock and Data).  
It is based on the original work [archived here](https://web.archive.org/web/20130921051232/http://www.astrorats.org/blog/2013/07/29/xbox-360-rf-module-and-the-raspberry-pi).

## Pinout

![Fat Xbox 360 RF Module Pinout](https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSkETPUjZ_rwXZraT7AbDlZyhII_qOqRYhAvA&s)

### Raspberry Pi → Xbox 360 RF Module
| Raspberry Pi | RF Module Pin | Function |
|--------------|--------------|----------|
| GPIO 24      | Pin 6        | Data     |
| GPIO 25      | Pin 7        | Clock    |
| 3V3          | Pin 1        | VCC      |
| GND          | Pin 4        | GND      |

### USB → Xbox 360 RF Module
| USB Signal | RF Module Pin | Function |
|------------|--------------|----------|
| D-         | Pin 2        | D-       |
| D+         | Pin 3        | D+       |
| GND        | Pin 4        | GND      |

## References
- [Xbox 360 RF Module controlled with Arduino](https://www.electromaker.io/project/view/xbox-360-rf-module-controlled-with-an-arduino-1?srsltid=AfmBOoqaIvXYYNZ5GorwITz8wOPjD5kLdt7DVYkYCu3CwfoVeJucyNF2)  
- [Xbox 360 Controller Receiver Project](https://agarmash.com/posts/xbox-360-controller-receiver/)  
- [Homemade Xbox 360 wireless receiver (Se7enSins forum)](https://www.se7ensins.com/forums/threads/how-to-make-a-homemade-xbox-360-controller-wireless-receiver-for-pc.668839/)  
