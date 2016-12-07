import RPi.GPIO as GPIO

class LED(object):

    def __init__(self, lichtwecker):

        self.lw = lichtwecker

        # get PIN Numbers
        self.RED = int(self.lw.config.value("red"))
        self.WARM_WHITE = int(self.lw.config.value("warm_white"))
        self.GREEN = int(self.lw.config.value("green"))

        # used for the self test / boot screen
        self.names = { 
            self.RED: "ROT",
            self.WARM_WHITE: "WARMWEISS",
            self.GREEN: "GRUEN"
        }


        # setup IO Ports and PWM
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        GPIO.setup(self.RED, GPIO.OUT, initial=GPIO.LOW) 
        GPIO.setup(self.WARM_WHITE, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.GREEN, GPIO.OUT, initial=GPIO.LOW)

        self.redPWM = GPIO.PWM(self.RED, 100)
        self.redPWM.start(0)
        self.greenPWM = GPIO.PWM(self.GREEN, 100)
        self.greenPWM.start(0)
        self.wharm_whitePWM = GPIO.PWM(self.WARM_WHITE, 100)
        self.wharm_whitePWM.start(0)

        self._led_to_pwm = { 
            self.RED: self.redPWM,
            self.WARM_WHITE: self.wharm_whitePWM,
            self.GREEN: self.greenPWM,
            }


    # retrieve color names, for pin numbers
    def name_for_led(self, led_pin):
        return self.names[led_pin]

    # set brightness for the LEDs
    def set_brightness(self, led, percentage):
        self._led_to_pwm[led].ChangeDutyCycle(percentage)
        # print ("set brightness led:{} brightness:{}".format(led, percentage))