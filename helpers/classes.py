from circuits import Component, Event, Timer
# from transitions import Machine, State
# import threading
import time
import logging
import helpers
import RPi.GPIO as GPIO

from easysettings import EasySettings

import configparser
import io
import os

#### CONSTANTS ####

CONF_FILE = "/etc/lichtwecker/lichtwecker.conf"

debug = False


#### HELPER CLASSES ####

class Config(object):
    """ little Helper to read in a static config file, here Lichtwecker's 
        basic config is set, like who owns it, to which IO ports buttons
        are connected and so on. This is not meant to store any state.
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

        self.lw = lichtwecker
        
        self.menubutton = int(self.lw.config.value("menubutton"))
        self.alarmbutton = int(self.lw.config.value("alarmbutton"))
        self.upbutton = int(self.lw.config.value("upbutton"))
        self.downbutton = int(self.lw.config.value("downbutton"))
        self.okbutton = int(self.lw.config.value("okbutton"))
        
        self.buttons = [
            self.menubutton,
            self.alarmbutton,
            self.upbutton,
            self.downbutton,
            self.okbutton,
            ]
        
        print ("Configged buttons: {}".format(self.buttons))
        
        # register getting informed on button down events
        self.register_button_handlers()

    
    def register_button_handlers(self):
        """Register Keypress callbacks for all our buttons on the Lichtwecker"""    
        for button in self.buttons:
            GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(button, GPIO.FALLING, callback=self.buttonpress_received, bouncetime=200)

    def buttonpress_received(self, button):
        # forward button press to Lichtwecker Class
        self.lw.buttonpress_received(button)

#### CIRCUITS EVENTS ####    

class start_component_event(Event):
    """ 
    start a component, use with a channel set, otherwise all will start at once
    which will produce quite weird behavior 
    """

class stop_component_event(Event):
    """ 
    stop a component, use with a channel set, otherwise all will die at once
    """

class component_done_event(Event):
    """ 
    sent by a component when it's done (add sender, to help main Class to identify who is done)
    """
    
class keypress(Event):
    """ 
    sent by Root Component to active Child, contains the pressed key.
    """

#### CIRCUITS COMPONENTS ####    

class Boot(Component):
    """
    This is the boot sequence of the Lichtwecker. Not booting in the traditional 
    sense, more greeting the Owner on the LCD and testing all LEDS plus Audio. 
    This is only called once at start of the Lichtwecker
    """

    BOOT_SONG = "dosem.mp3"

    def __init__(self, lichtwecker):
        Component.__init__(self)
        self.lw = lichtwecker
        self.channel = "boot"
        
    def start_component_event(self):
        #self.timer = Timer(1, Event.create("update_boot_screen"), persist=True).register(self)
        self.show_boot_sequence()
        
    def show_boot_sequence(self):
        self.lw.lcd.lcd_string("Hallo {}".format(self.lw.config.value("owner")), self.lw.lcd.LCD_LINE_1)

        time.sleep(1) 
        
        self.lw.lcd.lcd_string("gleich: SysTest", self.lw.lcd.LCD_LINE_2)

        time.sleep(3)

        self.lw.lcd.lcd_string("System Test", self.lw.lcd.LCD_LINE_1)
        self.lw.lcd.lcd_string("TON!", self.lw.lcd.LCD_LINE_2)
        self.lw.audio.playsingle(Boot.BOOT_SONG)
                
        time.sleep(3)

        for led in self.lw.led.names.keys():
            self.diminandoutled(led)
            time.sleep(1)
        
        # refresh MPD's audio Database
        self.lw.audio.stop()
        self.lw.audio.refresh_music_dir()    
        
        self.lw.lcd.lcd_string("FERTSCH!", self.lw.lcd.LCD_LINE_2)
        
        # inform lw instance, we are done
        self.fire(component_done_event(self), self.lw.channel)

    def diminandoutled(self, led):
        self.lw.lcd.lcd_string("System Test", self.lw.lcd.LCD_LINE_1)
        self.lw.lcd.lcd_string("LED: {0:>11}".format(self.lw.led.name_for_led(led)), self.lw.lcd.LCD_LINE_2)
        
        for brightness in range(1,101):
            self.lw.led.set_brightness(led, brightness)
            time.sleep(0.01)
        for brightness in range(100,-1, -1):
            self.lw.led.set_brightness(led, brightness)
            time.sleep(0.01)

class BaseLWComponent(Component):
    
    def __init__(self, lichtwecker):
        Component.__init__(self)
        self.lw = lichtwecker
        self.channel = self.name.lower()


class SetAlarm(BaseLWComponent):

    alarm_items = [  
                    {   
                        "line1":    "Zeit:  (Stunden)",
                        "store_as": "alarm_{0:d}_hours",
                        "min_val": 0,
                        "max_val": 23,
                        "formatstring": "{0:02d}h",
                    },
                    {   
                        "line1":    "Zeit:  (Minuten)",
                        "store_as": "alarm_{0:d}_minutes",
                        "min_val": 0,
                        "max_val": 59,
                        "formatstring": "{0:02d}m",
                    },
                    {   
                        "line1":    "Tage:",
                        "store_as": "alarm_{0:d}_trigger",
                        "min_val": 0,
                        "max_val": 2,
                        "possible_values": [ 
                            { "displayname": "Werktags", "value": "weekdays"},
                            { "displayname": "Wochenende", "value": "weekend"},
                            { "displayname": "jeden Tag", "value": "alldays"},
                        ]
                    },
                    {   
                        "line1":    "Licht:",
                        "store_as": "alarm_{0:d}_with_light",
                        "possible_values": [ 
                            { "displayname": "ein", "value": "on"},
                            { "displayname": "aus", "value": "off"},
                        ]
                    },
                    {   
                        "line1":    "Musik:",
                        "store_as": "alarm_{0:d}_title",
                    },
                  
                   ]

    
    def __init__(self, lichtwecker):
        BaseLWComponent.__init__(self, lichtwecker)

    def start_component_event(self, *args):
        # init menu pointer
        self.alarm_num = args[0]
        self.items_pointer = 0
        self.values = self.get_saved_settings()
        self.display_entry()
        
    def start_timer(self):
        self.timer = Timer(1, Event.create("blink_alarm_line"), persist=True).register(self)

    def display_entry(self, value_blanked = False):
        
        current_item = self.alarm_items[self.items_pointer]
        
        self.lw.lcd.lcd_string(current_item["line1"], self.lw.lcd.LCD_LINE_1)
        
        if (self.is_lookup_type(current_item)):
            self.lw.lcd.lcd_string(current_item["possible_values"][self.values[self.items_pointer]]["displayname"], self.lw.lcd.LCD_LINE_2)
        elif(self.items_pointer == 4):
            # special case music
            pass 
        elif("formatstring" in current_item):
            self.lw.lcd.lcd_string(current_item["formatstring"].format(self.values[self.items_pointer]), self.lw.lcd.LCD_LINE_2)
        else:
            self.lw.lcd.lcd_string(self.values[self.items_pointer], self.lw.lcd.LCD_LINE_2)
        
        # Need way to display title of music here. This is missing yet 
        
    def keypress(self, key):
        
#        self.timer.unregister()
        
        current_item = self.alarm_items[self.items_pointer]
        
        if (key == self.lw.buttons.upbutton):
            # hours and minutes mode
            if ((self.items_pointer == 0) or (self.items_pointer == 1)):
                self.values[self.items_pointer] += 1
                if (self.values[self.items_pointer] > current_item["max_val"]):
                    self.values[self.items_pointer] = current_item["min_val"]

            # lookup types
            if ((self.items_pointer == 2) or (self.items_pointer == 3)):
                self.values[self.items_pointer] += 1
                if (self.values[self.items_pointer] >= len(current_item["possible_values"])):
                    self.values[self.items_pointer] = 0 

            self.display_entry()

        if (key == self.lw.buttons.downbutton):
            # hours and minutes mode
            if ((self.items_pointer == 0) or (self.items_pointer == 1)):
                self.values[self.items_pointer] -= 1
                if (self.values[self.items_pointer] < current_item["min_val"]):
                    self.values[self.items_pointer] = current_item["max_val"]
            
            # lookup types
            if ((self.items_pointer == 2) or (self.items_pointer == 3)):
                self.values[self.items_pointer] -= 1
                if (self.values[self.items_pointer] < 0):
                    self.values[self.items_pointer] = len(current_item["possible_values"]) - 1

            self.display_entry()

        if (key == self.lw.buttons.okbutton):

            self.save_single_value()
            
            self.items_pointer += 1
            if (self.items_pointer >= len (self.alarm_items)):
                self.activate_alarm()
                self.fire(component_done_event(self))
            else:
                self.display_entry()
            
        if (key == self.lw.buttons.menubutton):
            self.items_pointer -= 1
            if (self.items_pointer < 0):
                self.items_pointer = 0
            self.display_entry()

    def save_single_value(self):
        
        current_item = self.alarm_items[self.items_pointer]
        
        if (self.is_lookup_type(current_item)):
            # Lookup value: uses values[items_pointer] as an index to the actual value
            value = current_item["possible_values"][self.values[self.items_pointer]]["value"]
        else:
            value = self.values[self.items_pointer] 
        print ("Saving key: {0} value: {1}".format(self.alarm_items[self.items_pointer]["store_as"].format(self.alarm_num), value))        
        self.lw.settings.setsave(self.alarm_items[self.items_pointer]["store_as"].format(self.alarm_num), value)

    def activate_alarm(self):

        # mark alarm as active (Rest was saved during rest of this class
        self.lw.settings.setsave("alarm_{0:d}_enabled".format(self.alarm_num), True)
        
        self.lw.lcd.lcd_string("Alarm {0:d}:".format(self.alarm_num), self.lw.lcd.LCD_LINE_1)
        self.lw.lcd.lcd_string("gespeichert!", self.lw.lcd.LCD_LINE_2)
        
    def is_lookup_type(self, item):
        return "possible_values" in item

    def get_saved_settings(self):
        
        values = [0] * len(self.alarm_items)
        
        print ("Settings for alarm {0:d} before readout: {1}".format(self.alarm_num, values))
        
        for item_idx, item in enumerate(self.alarm_items):
            setting_key = item["store_as"].format(self.alarm_num)
            print ("Setting for item {0:s}: {1:s}".format(item["line1"],setting_key))
            if (self.lw.settings.has_option(setting_key)):
                # only read in value, if it is stored in settings
                intermediate = self.lw.settings.get(setting_key)
                if (self.is_lookup_type(item)):
                    print ("item {0:s}: is lookup type".format(item["line1"]))
                    possible_values = item["possible_values"]
                    for lookup_index, value in enumerate(possible_values):
                        if (value["value"] == intermediate):
                            values[item_idx] = lookup_index
                            print ("Value retrieved: {}".format(lookup_index))
                else:
                    values[item_idx] = intermediate
                    print ("Value retrieved: {}".format(intermediate)) 


        print ("Settings for alarm {0:d}: {1}".format(self.alarm_num, values))
        return values

class RereadUsb(BaseLWComponent):
    
    def __init__(self, lichtwecker):
        BaseLWComponent.__init__(self, lichtwecker)
        
    def start_component_event(self):
        self.display_reread_usb()
        self.counter = 0
        self.timer = Timer(1, Event.create("blink"), persist=True).register(self)

    def blink(self):
        hidden = self.counter % 2 == 0
        self.counter += 1
        self.display_reread_usb(hidden)
        
    def display_reread_usb(self, hidden = False):
        
        self.lw.lcd.lcd_string("USB neu einlesen", self.lw.lcd.LCD_LINE_1)
        if (hidden):
            self.lw.lcd.lcd_string("", self.lw.lcd.LCD_LINE_2)
        else:
            self.lw.lcd.lcd_string("Start", self.lw.lcd.LCD_LINE_2)
        
    def keypress(self, key):
        
        self.timer.unregister()
            
        if (key == self.lw.buttons.menubutton):
            self.lw.lcd.lcd_string("abgebrochen", self.lw.lcd.LCD_LINE_2)
            self.fire(component_done_event(self))
            
        if (key == self.lw.buttons.okbutton):
            self.lw.lcd.lcd_string("gestartet...", self.lw.lcd.LCD_LINE_2)
            self.lw.audio.refresh_music_dir()
            if (debug): print ("Titel: {}".format(self.lw.audio.get_titles_info()))
            titlelist = self.lw.audio.get_titles_info()
            titlecount = len (titlelist)
            self.lw.lcd.lcd_string("gefunden: {0:d}".format(titlecount), self.lw.lcd.LCD_LINE_2)
            time.sleep(3)
            self.lw.lcd.lcd_string("fertig", self.lw.lcd.LCD_LINE_2)
            self.fire(component_done_event(self))

class SetSnooze(BaseLWComponent):
    
    def __init__(self, lichtwecker):
        BaseLWComponent.__init__(self, lichtwecker)

    def start_component_event(self):
        # init menu pointer
        self.snooze = self.lw.settings.get("snooze")
        self.display_entry()
        self.counter = 0
        self.start_timer()
        
    def start_timer(self):
        self.timer = Timer(1, Event.create("blink_snooze_line"), persist=True).register(self)
        
    def blink_snooze_line(self):
        pair = self.counter % 2 == 0

        if pair:
            self.lw.lcd.lcd_string("   min", self.lw.lcd.LCD_LINE_2)
        else:
            self.lw.lcd.lcd_string("{0:2d} min".format(self.snooze), self.lw.lcd.LCD_LINE_2)
    
        self.counter += 1

    def keypress(self, key):
        
        self.timer.unregister()
        
        if (key == self.lw.buttons.upbutton):
            self.snooze += 5
            if (self.snooze > 90):
                self.snooze = 90
            self.display_entry()
            self.start_timer()

        if (key == self.lw.buttons.downbutton):
            self.snooze -= 5
            if (self.snooze < 5):
                self.snooze = 5
            self.display_entry()
            self.start_timer()
            
        if (key == self.lw.buttons.okbutton):
            # send event to root component, that we are done 
            # and that entry current_entry has been chosen
            self.lw.settings.setsave("snooze", self.snooze)
            self.lw.lcd.lcd_string("gespeichert...", self.lw.lcd.LCD_LINE_2)
            self.fire(component_done_event(self))

    def display_entry(self):
        self.lw.lcd.lcd_string("Schlummern:", self.lw.lcd.LCD_LINE_1)
        self.lw.lcd.lcd_string("{0:2d} min".format(self.snooze), self.lw.lcd.LCD_LINE_2)

class Menu(Component):
    """ This Component handles the menu, which gets 
        displayed when the Menu button is pressed
    """
    menu_items = [  
                    {   
                        "display":      "Alarm 1 setzen",
                        "component":    "SetAlarm",
                        "params":       1
                    },
                    {   
                        "display":      "Alarm 2 setzen",
                        "component":    "SetAlarm",
                        "params":       2
                    },
                    {   
                        "display":      "Schlummerzeit",
                        "component":    "SetSnooze",
                    },
                    {   
                        "display":      "Musik einlesen",
                        "component":    "RereadUSB",
                    },
                    {   
                        "display":       "Menu verlassen",
                    },
                  
                   ]

    def __init__(self, lichtwecker):
        
        Component.__init__(self)
        self.lw = lichtwecker
        
        # set the channel to be "clock", so it receives only Events addressed to it
        self.channel = "menu"

        
    def start_component_event(self):
        # init menu pointer
        print ("Menu Start received")
        self.current_entry = 0
        self.display_menu()
        
    def display_menu(self):
        self.lw.lcd.lcd_string("Einstellungen <>", self.lw.lcd.LCD_LINE_1)
        self.lw.lcd.lcd_string(self.menu_items[self.current_entry]["display"], self.lw.lcd.LCD_LINE_2)

    def keypress(self, key, *args):
        
        if (key == self.lw.buttons.downbutton):
            self.current_entry += 1
            if (self.current_entry >= len(self.menu_items)):
                self.current_entry = 0
            self.display_menu()
        if (key == self.lw.buttons.upbutton):
            self.current_entry -= 1
            if (self.current_entry < 0):
                self.current_entry = len (self.menu_items) - 1
            self.display_menu()
        if (key == self.lw.buttons.okbutton):
            # send event to root component, that we are done 
            # and that entry current_entry has been chosen
            self.lw.lcd.lcd_string("gehe zurueck...", self.lw.lcd.LCD_LINE_2)
            self.fire(component_done_event(self, self.current_entry))

class Clock(Component):
    """ the clock component, it displays time, alarm time and checks if an alarm is due"""

    def __init__(self, lichtwecker):
        
        Component.__init__(self)
        self.lw = lichtwecker

        # set the channel to be "clock", so it receives only Events addressed to it
        self.channel = "clock"

        self.counter = 0
        
    def start_component_event(self, *args):
        print ("Clock start event received")
        self.timer = Timer(1, Event.create("update_clock_screen"), persist=True).register(self)

    def keypress(self, key, *args):

        print ("Keypress in Clock: {}".format(key))

        if (key == self.lw.buttons.menubutton):
            print ("MenuButton Pressed")
            self.timer.unregister()
            self.fire(component_done_event(self, "menu"))
        if (key == self.lw.buttons.upbutton):
            pass
        if (key == self.lw.buttons.okbutton):
            pass
    
    def update_clock_screen(self, *args):

        pair = self.counter % 2 == 0

        if pair:
            datetimestring = time.strftime("%H:%M   %d.%m.%y") 
        else:
            datetimestring = time.strftime("%H %M   %d.%m.%y") 

        self.lw.lcd.lcd_string(datetimestring, self.lw.lcd.LCD_LINE_1)
        self.lw.lcd.lcd_string("    wecken:08:00", self.lw.lcd.LCD_LINE_2)

        self.counter += 1


class LichtWecker(Component):
    """ Main class of the LichtWecker, it creates and holds all helper classes
     
        """
    def __init__(self):

        # self.channel = "lichtwecker"

        self.states = [
                        { "name": "boot",
                        },
                        { "name": "clock",
                        },
                        { "name": "menu",
                        },
                        { "name": "setsnooze",
                        },
                       ]

        Component.__init__(self)

        logging.basicConfig(filename='lw.log', level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s) %(message)s',
                    )
        
        # Lichtwecker can be booting and idling at the moment
        print ("Initializer of Lichtwecker")

        # Initialize Helper Classes
        self.config = Config() # config must be first
        self.settings = EasySettings('lichtwecker.settings', name='LichtWecker', version='1.0')
        if (not self.settings.has_option("firstrun")):
            self.initialize_settings() 
        self.audio = helpers.Audio()
        self.led = helpers.LED(self)
        self.lcd = helpers.Display()
        self.buttons = Buttons(self)

        # register Components
        self.clock = Clock(self).register(self)
        self.menu = Menu(self).register(self)
        self.boot = Boot(self).register(self)
        self.setsnooze = SetSnooze(self).register(self)
        self.setalarm = SetAlarm(self).register(self)
        self.rereadusb = RereadUsb(self).register(self)

#### EVENT HANDLERS ####

    def started(self, *args):

        # let's start the Lichtwecker with the "boot" state
        #self.current_state = "boot"
        self.current_state = "clock"
        self.fire(start_component_event(), self.current_state)
        
    def component_done_event(self, sender, *args):

        if (len(args) > 0 ):
            print ("Component Done: {0:s} Parameter: {1}".format(sender.channel, args[0]))  
        else:
            print ("Component Done: {}".format(sender.channel))

        if (sender.channel == "boot"):
            self.start_state("clock")

        if (sender.channel == "clock"):
            self.start_state(args[0])

        if (sender.channel == "rereadusb"):
            self.start_state("clock")
            
        if (sender.channel == "setsnooze"):
            self.start_state("clock")

        if (sender.channel == "setalarm"):
            self.start_state("clock")

        if (sender.channel == "menu"):
            selected_menu_entry = args[0]
            menuentry = sender.menu_items[selected_menu_entry]
            if ("component" not in menuentry):
                # no menu entry selected, go back to clock
                self.start_state("clock")
            else: 
                newstate = menuentry["component"].lower()
                if ("params" in menuentry):
                    self.start_state(newstate, menuentry["params"])
                else:
                    self.start_state(newstate)

    # called from Button Class. when a button was pressed 
    def buttonpress_received(self, key):
        print ("Button pressed, will send key: {0:d} to : {1:s}".format(key, self.current_state))
        self.fire(keypress(key), self.current_state)
        
    def registered(self, *args):
        print ("Registered aus Lichtwecker. Parent: {0:s} -> Child: {1:s}".format(args[1].name, args[0].name))

    def unregistered(self, *args):
        print ("Unregistered aus Lichtwecker. Parent: {0:s} -> Child: {1:s}".format(args[1].name, args[0].name))

    def start_state(self, newstate, *args):
        
        print ("Starting new state: {}".format(newstate))
        self.current_state = newstate
        if (len(args) > 0):
            self.fire(start_component_event(args[0]), self.current_state)
        else:
            self.fire(start_component_event(), self.current_state)

        
    def initialize_settings(self):
        
        print ("This is Lichtweckers very first start, so we need to populate the settings file")
        self.settings.setsave ("firstrun", False)
        self.settings.setsave ("snooze", 5)
        
        
    """ 

    Überreste

    def on_enter_menu(self):
        self.lcd.lcd_string("SETTINGS:     <>", self.lcd.LCD_LINE_1)
        self.lcd.lcd_string("Alarm 1", self.lcd.LCD_LINE_2)
        
        
    """