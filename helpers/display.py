import RPi.GPIO as GPIO
import time

'''

LLCDHelper 

'''


class Display:
    """ This class encapsulated the Display """

    # Define GPIO to LCD mapping
    LCD_RS = 7
    LCD_E  = 8
    LCD_D4 = 25
    LCD_D5 = 24
    LCD_D6 = 23
    LCD_D7 = 18

    # Define some device constants
    LCD_WIDTH = 16    # Maximum characters per line
    LCD_CHR = True
    LCD_CMD = False

    LCD_LINE_1 = 0x80 # LCD RAM address for the 1st line
    LCD_LINE_2 = 0xC0 # LCD RAM address for the 2nd line

    # Timing constants
    E_PULSE = 0.0005
    E_DELAY = 0.0005

    def __init__(self):
        self.setup_gpio()
        self.initializeLcdDisplay()
    
    def setup_gpio(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)       # Use BCM GPIO numbers
        GPIO.setup(self.LCD_E, GPIO.OUT)  # E
        GPIO.setup(self.LCD_RS, GPIO.OUT) # RS
        GPIO.setup(self.LCD_D4, GPIO.OUT) # DB4
        GPIO.setup(self.LCD_D5, GPIO.OUT) # DB5
        GPIO.setup(self.LCD_D6, GPIO.OUT) # DB6
        GPIO.setup(self.LCD_D7, GPIO.OUT) # DB7

    def initializeLcdDisplay(self):
        # Initialise display
        self.lcd_byte(0x33,self.LCD_CMD) # 110011 Initialise
        self.lcd_byte(0x32,self.LCD_CMD) # 110010 Initialise
        self.lcd_byte(0x06,self.LCD_CMD) # 000110 Cursor move direction
        self.lcd_byte(0x0C,self.LCD_CMD) # 001100 Display On,Cursor Off, Blink Off
        self.lcd_byte(0x28,self.LCD_CMD) # 101000 Data length, number of lines, font size
        self.lcd_byte(0x01,self.LCD_CMD) # 000001 Clear display
        time.sleep(self.E_DELAY)

    def lcd_byte(self, bits, mode):
        # Send byte to data pins
        # bits = data
        # mode = True  for character
        #        False for command

        GPIO.output(self.LCD_RS, mode) # RS

        # High bits
        GPIO.output(self.LCD_D4, False)
        GPIO.output(self.LCD_D5, False)
        GPIO.output(self.LCD_D6, False)
        GPIO.output(self.LCD_D7, False)
        if bits&0x10==0x10:
            GPIO.output(self.LCD_D4, True)
        if bits&0x20==0x20:
            GPIO.output(self.LCD_D5, True)
        if bits&0x40==0x40:
            GPIO.output(self.LCD_D6, True)
        if bits&0x80==0x80:
            GPIO.output(self.LCD_D7, True)

        # Toggle 'Enable' pin
        self.lcd_toggle_enable()

        # Low bits
        GPIO.output(self.LCD_D4, False)
        GPIO.output(self.LCD_D5, False)
        GPIO.output(self.LCD_D6, False)
        GPIO.output(self.LCD_D7, False)
        if bits&0x01==0x01:
            GPIO.output(self.LCD_D4, True)
        if bits&0x02==0x02:
            GPIO.output(self.LCD_D5, True)
        if bits&0x04==0x04:
            GPIO.output(self.LCD_D6, True)
        if bits&0x08==0x08:
            GPIO.output(self.LCD_D7, True)

        # Toggle 'Enable' pin
        self.lcd_toggle_enable()

    def lcd_toggle_enable(self):
        # Toggle enable
        time.sleep(self.E_DELAY)
        GPIO.output(self.LCD_E, True)
        time.sleep(self.E_PULSE)
        GPIO.output(self.LCD_E, False)
        time.sleep(self.E_DELAY)

    def lcd_string(self,message,line):
        # Send string to display
        message = message.ljust(self.LCD_WIDTH," ")
        self.lcd_byte(line, self.LCD_CMD)

        for i in range(self.LCD_WIDTH):
            self.lcd_byte(ord(message[i]),self.LCD_CHR)
