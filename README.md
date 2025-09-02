# Xbox 360 RF Module sync manager
this python script enables sync mode on a xbox 360 fat rf module using pin clock and data and raspberry pi gpio

this is an updated version of the code found here:
https://web.archive.org/web/20130921051232/http://www.astrorats.org/blog/2013/07/29/xbox-360-rf-module-and-the-raspberry-pi

this is the pinout

![Fat Xbox 360 RF Module Pinout](https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSkETPUjZ_rwXZraT7AbDlZyhII_qOqRYhAvA&s)

```bash
RaspberryPi      Xbox 360 RF Module
GPIO 24       -> Data  (pin 6)
GPIO 25       -> Clock (pin 7)
3V3:          -> VCC   (pin 1)
GND           -> GND   (pin 4)

USB              Xbox 360 RF Module
D-            -> D- (pin 2)
D+            -> D+ (pin 3)
GND           -> GND (pin 4 or any other GND point on the module)
```
