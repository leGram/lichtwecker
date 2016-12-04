from circuits import Component, Event, Timer
# from transitions import Machine, State
# import threading
import time
import logging
import helpers
import RPi.GPIO as GPIO

import configparser
import io
import os

#### CONSTANTS ####

CONF_FILE = "/etc/lichtwecker/lichtwecker.conf"

#### HELPER CLASSES ####

class Config(object):
    """ little Helper to read in a config file, here Lichtwecker's 
        basic config is set, like who owns it, to which IO ports buttons
        are connected and so on. 
        """
    def __init__(self):
        self._props = self._read_properties_file(CONF_FILE)

    def value(self, key):
        return self._props[key]

    def _read_properties_file(self,file_path):
        with open(file_path) as f:
            config = io.StringIO()
            config.write('[dummy_section]\n')
            config.write(f.read().replace('%', '%%'))
            config.seek(0, os.SEEK_SET)

            cp = configparser.SafeConfigParser()
            cp.readfp(config)

            return dict(cp.items('dummy_section'))

class Buttons(object):
    """ setting up the IO Ports for the Buttons and registering a callback, 
        when they get pressed (coupled with lichtwecker Class)
    """
    
    def __init__(self, lichtwecker):
        # keep a reference to the main lichtwecker
        self.lichtwecker = lichtwecker
        
        self.menubutton = int(lichtwecker.config.value("menubutton"))
        self.alarmbutton = int(lichtwecker.config.value("alarmbutton"))
        self.upbutton = int(lichtwecker.config.value("upbutton"))
        self.downbutton = int(lichtwecker.config.value("downbutton"))
        self.okbutton = int(lichtwecker.config.value("okbutton"))
        
        self.buttons = [
            self.menubutton,
            self.alarmbutton,
            self.upbutton,
            self.downbutton,
            self.okbutton,
            ]
        
        # register getting informed on button down events
        self.register_button_handlers()

    
    def register_button_handlers(self):
        """Register Keypress callbacks for all our buttons on the Lichtwecker"""    
        for button in self.buttons:
            GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(button, GPIO.FALLING, callback=self.buttonpress_received, bouncetime=200)

    def buttonpress_received(self, button):
        # forward button press to Lichtwecker Class
        self.lichtwecker.buttonpress_received(button)


#### CIRCUITS COMPONENTS ####    

class Menu(Component):
    """ This Component handles the menu, which gets 
        displayed when the Menu button is pressed
    """
    menu_items = [  
                    {   
                        "display":       "Edit Alarm 1",
                        "class_to_call": "SetAlarm",
                        "class_param": 1
                    },
                    {   
                        "display":       "Edit Alarm 2",
                        "class_to_call": "SetAlarm",
                        "class_param": 2
                    },
                    {   
                        "display":       "Schlummerzeit",
                        "class_to_call": "SetSnooze",
                    },
                   ]

    def __init__(self, lichtwecker):
        
        Component.__init__(self)
        
        # ref to lichtwecker
        self.lcd = lichtwecker.lcd
        
        # init menu pointer
        self.currentEntry = 0

class start_clock_event(Event):
    """ the goto clock event"""

class Clock(Component):
    """ the clock component, it displays time, alarm time and checks if an alarm is due"""

    def __init__(self, *args):
        
        Component.__init__(self)

        self.counter = 0
        self.lichtwecker = args[0]
        print ("Clock inited (should only happen once!)")
    
    def started(self, *args):
        pass
    
    def registered(self, *args):
        #print ("Clock component did register (should only happen once!)")
        pass
    
    def start_clock_event(self, *args):
        print ("Clock started")
        Timer(1, Event.create("update_clock_screen"), persist=True).register(self)
    
    def update_clock_screen(self, *args):

        logging.debug("Clock in update")
        
        pair = self.counter % 2 == 0

        if pair:
            datetimestring = time.strftime("%H:%M   %d.%m.%y") 
        else:
            datetimestring = time.strftime("%H %M   %d.%m.%y") 

        self.lichtwecker.lcd.lcd_string(datetimestring, self.lichtwecker.lcd.LCD_LINE_1)
        self.lichtwecker.lcd.lcd_string("    wecken:08:00", self.lichtwecker.lcd.LCD_LINE_2)

        self.counter += 1

class LichtWecker(Component):
    """ Main class of the LichtWecker, it creates and holds all helper classes
     
        """
    def __init__(self):

        Component.__init__(self)

        logging.basicConfig(filename='lichtwecker.log', level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s) %(message)s',
                    )
        
        # Lichtwecker can be booting and idling at the moment
        print ("Initializer of Lichtwecker")

        # Initialize Helper Classes
        self.lcd = helpers.Display()
        self.config = Config()
        self.buttons = Buttons(self)
        self.clock = Clock(self).register(self)
        self.menu = Menu(self).register(self)

        # register components

    def started(self, *args):
        # Transition to boot state
        print ("Lichtwecker in started")
        self.fire(start_clock_event()) # shows the clock


    # called. when a button is pressed via Button Class
    def buttonpress_received(self, key):
        logging.debug("button was pressed: {}".format(key))
        if (key == self.buttons.menubutton): 
            pass
        if (key == self.buttons.upbutton):
            pass

    def on_enter_boot(self):
        print ("We should now boot up ...")
        self.lcd.lcd_string("Hallo {}".format(self.config.value("owner")), self.lcd.LCD_LINE_1)
        time.sleep(2) 
        
        """
        Willkommens Meldung
        Einlesen der Konfiguration
        Test aller leuchtenden Dinge (eins nach dem anderen an und aus, ausgabe was geschieht
        Test Audio (spezielle Nachricht)
        """
        

    """ 

    Überreste

    def on_enter_menu(self):
        self.lcd.lcd_string("SETTINGS:     <>", self.lcd.LCD_LINE_1)
        self.lcd.lcd_string("Alarm 1", self.lcd.LCD_LINE_2)
        
        
    """