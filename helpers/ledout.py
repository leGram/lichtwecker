import RPi.GPIO as GPIO

class LED:

    def __init__(self):

        self.RED = 3
        self.WARM_WHITE = 4
        self.GREEN = 2

        GPIO.setwarnings(True)
        GPIO.setmode(GPIO.BCM)       # Use BCM GPIO numbers
        GPIO.setup(self.RED, GPIO.OUT, initial=GPIO.LOW) 

        self.redPWM = GPIO.PWM(self.RED, 100)
        self.redPWM.start(0)

        GPIO.setup(self.WARM_WHITE, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.GREEN, GPIO.OUT, initial=GPIO.LOW)

#    def red(self,onoff):
#    GPIO.output(self.RED, onoff)

    def red_pwm(self, percentage):
        self.redPWM.ChangeDutyCycle(percentage)

    def green(self,onoff):
        GPIO.output(self.GREEN, onoff)

    def warm_white(self,onoff):
        GPIO.output(self.WARM_WHITE, onoff)



