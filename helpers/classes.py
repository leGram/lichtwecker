from circuits import Component, Event, Timer
# from transitions import Machine, State
# import threading
import time
import logging
import helpers
import RPi.GPIO as GPIO

from easysettings import EasySettings
import datetime # fuer Alarm Class
import locale
import configparser
import io
import os
from signal import alarm

from pathlib import Path
import shutil
import subprocess

#### CONSTANTS ####

CONF_FILE = "/etc/lichtwecker/lichtwecker.conf"

debug = True

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
        
        if (debug): print ("Configged buttons: {}".format(self.buttons))
        
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
    sent by Root Component to activate a Child, contains the pressed key.
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
        
        # Turn LCD BG Light on
        self.lw.led.set_brightness(self.lw.led.LCD_BG, 100)
        
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
            
        if (led == self.lw.led.LCD_BG):
            self.lw.led.set_brightness(led, 100)

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
        self.music = self.lw.audio.get_titles_info()
        
    #def start_timer(self):
    #    self.timer = Timer(1, Event.create("blink_alarm_line"), persist=True).register(self)

    def display_entry(self, value_blanked = False):
        
        current_item = self.alarm_items[self.items_pointer]
        
        self.lw.lcd.lcd_string(current_item["line1"], self.lw.lcd.LCD_LINE_1)
        
        if (self.is_lookup_type(current_item)):
            self.lw.lcd.lcd_string(current_item["possible_values"][self.values[self.items_pointer]]["displayname"], self.lw.lcd.LCD_LINE_2)
        elif(self.items_pointer == 4):
            # special case music
            print ("Music: {}".format([self.values[self.items_pointer]]))
            music_title = self.music[self.values[self.items_pointer]]["title"]
            self.lw.lcd.lcd_string(music_title, self.lw.lcd.LCD_LINE_2) 
        elif("formatstring" in current_item):
            self.lw.lcd.lcd_string(current_item["formatstring"].format(self.values[self.items_pointer]), self.lw.lcd.LCD_LINE_2)
        else:
            self.lw.lcd.lcd_string(self.values[self.items_pointer], self.lw.lcd.LCD_LINE_2)
        
        # Need way to display title of music here. This is missing yet 
        
    def keypress(self, key):
        
#        self.timer.unregister()
        
        current_item = self.alarm_items[self.items_pointer]
        
        if (key == self.lw.buttons.downbutton):
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

            # music
            if (self.items_pointer == 4):
                self.values[self.items_pointer] += 1
                if (self.values[self.items_pointer] >= len(self.music)):
                    self.values[self.items_pointer] = 0

            self.display_entry()

        if (key == self.lw.buttons.upbutton):
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

            # music
            if (self.items_pointer == 4):
                self.values[self.items_pointer] -= 1
                if (self.values[self.items_pointer] < 0):
                    self.values[self.items_pointer] = len(self.music) - 1

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
        if (debug): print ("Saving key: {0} value: {1}".format(self.alarm_items[self.items_pointer]["store_as"].format(self.alarm_num), value))        
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
        
        if (debug): print ("Settings for alarm {0:d} before readout: {1}".format(self.alarm_num, values))
        
        for item_idx, item in enumerate(self.alarm_items):
            setting_key = item["store_as"].format(self.alarm_num)
            if (debug): print ("Setting for item {0:s}: {1:s}".format(item["line1"],setting_key))
            if (self.lw.settings.has_option(setting_key)):
                # only read in value, if it is stored in settings
                intermediate = self.lw.settings.get(setting_key)
                if (self.is_lookup_type(item)):
                    if (debug): print ("item {0:s}: is lookup type".format(item["line1"]))
                    possible_values = item["possible_values"]
                    for lookup_index, value in enumerate(possible_values):
                        if (value["value"] == intermediate):
                            values[item_idx] = lookup_index
                            if (debug): print ("Value retrieved: {}".format(lookup_index))
                else:
                    values[item_idx] = intermediate
                    if (debug): print ("Value retrieved: {}".format(intermediate)) 


        if (debug): print ("Settings for alarm {0:d}: {1}".format(self.alarm_num, values))
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
        
        if (key == self.lw.buttons.downbutton):
            self.snooze += 1
            if (self.snooze > 30):
                self.snooze = 30
            self.display_entry()
            self.start_timer()

        if (key == self.lw.buttons.upbutton):
            self.snooze -= 1
            if (self.snooze < 1):
                self.snooze = 1
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



class ReadWlanConfig(BaseLWComponent):
    
    def __init__(self, lichtwecker):
        BaseLWComponent.__init__(self, lichtwecker)
        self.wlanfilepathonstick = "/media/usbstick/wpa_supplicant.conf"
        self.wlanfileonpi = "/etc/wpa_supplicant/wpa_supplicant.conf"

    def start_component_event(self):

        self.display_entry()
        
    def keypress(self, key):
        
        if (key == self.lw.buttons.menubutton):
            self.lw.lcd.lcd_string("ABBRUCH", self.lw.lcd.LCD_LINE_2)
            self.fire(component_done_event(self))

        if (key == self.lw.buttons.okbutton):

            # read WLAN cfg file from USB and copy it to the right place
            self.lw.lcd.lcd_string("Suche Datei...", self.lw.lcd.LCD_LINE_2)
            if (self.wlan_file_found()):
                self.lw.lcd.lcd_string("gefunden", self.lw.lcd.LCD_LINE_2)
                time.sleep(1)
                self.lw.lcd.lcd_string("kopiere...", self.lw.lcd.LCD_LINE_2)
                self.copy_file()
                self.lw.lcd.lcd_string("kopiert", self.lw.lcd.LCD_LINE_2)
                time.sleep(1)
                self.lw.lcd.lcd_string("reset WLAN...", self.lw.lcd.LCD_LINE_2)
                self.reset_interface()
                self.lw.lcd.lcd_string("WLAN restarted", self.lw.lcd.LCD_LINE_2)
                time.sleep(1)
                self.lw.lcd.lcd_string("warte 5sec(DHCP)", self.lw.lcd.LCD_LINE_2)
                time.sleep(5)
                try:
                    output = subprocess.check_output(["hostname","-I"])
                except:
                    output = "ip query failed"
                self.lw.lcd.lcd_string("IP Adresse:", self.lw.lcd.LCD_LINE_1)
                self.lw.lcd.lcd_string("{}".format(output.decode('UTF-8')), self.lw.lcd.LCD_LINE_2)
                time.sleep(3)
                self.lw.lcd.lcd_string("Fertig", self.lw.lcd.LCD_LINE_2)

            else:
                self.lw.lcd.lcd_string("nicht gefunden!", self.lw.lcd.LCD_LINE_2)

            self.fire(component_done_event(self))

    def wlan_file_found(self):

        wlanfile = Path(self.wlanfilepathonstick)
        if wlanfile.is_file():
            return True
        else:
            return False
    
    def copy_file(self):
        shutil.copy(self.wlanfilepathonstick, self.wlanfileonpi)

    def reset_interface(self):
        subprocess.call(["ifdown","wlan0"])
        subprocess.call(["ifup","wlan0"])
        
    def display_entry(self):
        self.lw.lcd.lcd_string("WLAN Konfig:", self.lw.lcd.LCD_LINE_1)
        self.lw.lcd.lcd_string("OK fuer Start...", self.lw.lcd.LCD_LINE_2)

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
                        "display":      "WLAN CFG laden",
                        "component":    "ReadWlanConfig",
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
        if (debug): print ("Menu Start received")
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
        self.alarms = 0
        self.lightison = False
        self.alarm_in_progress_time = None
        
    def start_component_event(self, *args):
        if (debug): print ("Clock start event received")
        self.timer = Timer(1, Event.create("update_clock_screen"), persist=True).register(self)

        # retrieve, if alarms are enabled (Alarm 1 and to get OR'ed together       
        if self.lw.settings.has_option('alarm_1_enabled'):
            if(self.lw.settings.get("alarm_1_enabled")):
                self.alarms = self.alarms | 1
        else: 
            self.alarms = self.alarms & 2
                
        if self.lw.settings.has_option('alarm_2_enabled'):
            if(self.lw.settings.get("alarm_2_enabled")):
                self.alarms = self.alarms | 2
        else: 
            self.alarms = self.alarms & 1

        # get LCD Brightness from Setting
        self.lcd_brightness = self.lw.settings.get("lcd_brightness")
        self.lw.led.set_brightness(self.lw.led.LCD_BG, self.lcd_brightness)

    def keypress(self, key, *args):

        if (debug): print ("Keypress in Clock: {}".format(key))

        if (key == self.lw.buttons.menubutton):
            if (debug): print ("MenuButton Pressed")
            self.timer.unregister()
            self.fire(component_done_event(self, "menu"))
        
        if (key == self.lw.buttons.downbutton):
            self.modify_lcd_brightness(+2)

        if (key == self.lw.buttons.upbutton):
            self.modify_lcd_brightness(-2)

        if (key == self.lw.buttons.okbutton):
            self.setlight(not self.lightison) 
            
        if (key == self.lw.buttons.alarmbutton):
            # mark alarm as active (Rest was saved during rest of this class
            self.alarms +=1
            if (self.alarms > 3):
                self.alarms = 0
            self.write_alarms()
            self.update_clock_screen()
    
    def update_clock_screen(self, *args):

        pair = self.counter % 2 == 0

        if pair:
            datetimestring = time.strftime("%H:%M   %d.%m.%y") 
        else:
            datetimestring = time.strftime("%H %M   %d.%m.%y") 

        self.lw.lcd.lcd_string(datetimestring, self.lw.lcd.LCD_LINE_1)
        
        if (self.alarms == 3):
            alarms_active_string = "A1,A2"
        elif (self.alarms == 1):
            alarms_active_string = "A1"
        elif (self.alarms == 2):
            alarms_active_string = "A2"
        else: 
            alarms_active_string = ""

        alarm1 = Alarm.from_settings(1, self.lw.settings)
        alarm2 = Alarm.from_settings(2, self.lw.settings)
        
        print ("Active Alarms:{}".format(self.alarms))
        
        if (debug): print ("Alarm1: {}".format(alarm1))
        if (debug): print ("Alarm2: {}".format(alarm2))
        
        if (self.alarms == 3):
            if (alarm1 < alarm2):
                self.next_alarm = alarm1
            else:
                self.next_alarm = alarm2
        
        elif (self.alarms == 2):
            self.next_alarm = alarm2
        elif (self.alarms == 1):
            self.next_alarm = alarm1
        else:
            self.next_alarm = None
        
        print ("Self next alarm = {}".format(self.next_alarm))
        
        if (self.next_alarm is None):
            nextwaketime = ""
        else:    
            nextwaketime = self.next_alarm.get_time_as_string()
        
        self.lw.lcd.lcd_string("{0:<5s}{1:>11s}".format(alarms_active_string, nextwaketime), self.lw.lcd.LCD_LINE_2)

        self.counter += 1
        
        alarm_mins = self.next_alarm.alarm_in_minutes()
        
        if (debug): print ("Alarm in minutes: {0:d}".format(alarm_mins))
        if (debug): print ("Alarm with lights: {}".format(self.next_alarm.with_light))
        
        
        
        if (self.next_alarm.with_light == "on"):
            if (alarm_mins <=30):
                self.start_alarmhandler(self.next_alarm)
        else:
            if (alarm_mins <=0):
                self.start_alarmhandler(self.next_alarm)
                
        
    def start_alarmhandler(self, alarm):

        if (debug): print ("start AlarmHandler")
        
        if (self.alarm_in_progress_time is None):
            # no alarm was triggered ever, so trigger this one
            self.alarm_in_progress_time = alarm.alarmtime()
            self.timer.unregister()
            self.fire(component_done_event(self, "alarmhandler", alarm))
        elif(self.alarm_in_progress_time == alarm.alarmtime()):
            # This alarm was handled already, skip it
            return
        else:
            # other alarm was triggered in past, but not this one, so trigger this one
            self.alarm_in_progress_time = alarm.alarmtime()
            self.timer.unregister()
            self.fire(component_done_event(self, "alarmhandler", alarm))
            
    def setlight(self, to_state):
        
        if (to_state):
            newVal = 100
        else:
            newVal = 0

        self.lw.led.set_brightness(self.lw.led.RED, 0)
        self.lw.led.set_brightness(self.lw.led.GREEN, 0)
        self.lw.led.set_brightness(self.lw.led.WARM_WHITE, newVal)
        
        self.lightison = to_state

    def modify_lcd_brightness(self, amount):
        
        self.lcd_brightness += amount
        
        if (self.lcd_brightness > 100):
            self.lcd_brightness = 100

        if (self.lcd_brightness < 0):
            self.lcd_brightness = 0

        self.lw.led.set_brightness(self.lw.led.LCD_BG, self.lcd_brightness)
        self.lw.settings.setsave ("lcd_brightness", self.lcd_brightness)
        
        if (debug): print ("changed LCD brightness to {0:d}".format(self.lcd_brightness))

    ##### ALARM FUNCTIONS #####

    def write_alarms(self):
        if (self.alarms & 2):
            # mark alarm as active (Rest was saved during rest of this class
            self.lw.settings.setsave("alarm_2_enabled", True)
        else:
            self.lw.settings.setsave("alarm_2_enabled", False)
        
        if (self.alarms & 1):
            # mark alarm as active (Rest was saved during rest of this class
            self.lw.settings.setsave("alarm_1_enabled", True)
        else:
            self.lw.settings.setsave("alarm_1_enabled", False)

    def get_next_alarm_time_as_string(self):
        
        # no alarm active, so no time
        if (self.alarms == 0):
            return ""
        
        if (self.alarms == 3):
            # both alarms are active, so we need to figure, which one is closer
            alarm1 = Alarm.retrieve_alarm_from_settings(1, self.lw.settings)
            alarm2 = Alarm.retrieve_alarm_from_settings(2, self.lw.settings)
            if (alarm1 < alarm2):
                alarm_to_display = alarm1
            else: 
                alarm_to_display = alarm2
        else:
            alarm_to_display = Alarm.retrieve_alarm_from_settings(self.alarms, self.lw.settings)
        

class AlarmHandler(BaseLWComponent):
    
    # re-check interval in seconds (once per minute)
    TIMER_INTERVAL = 2  
    # 
    MAX_ALARM_TIME_IN_MINUTES = 60

    DISPLAY_REFRESH_INTERVAL = 30 # display refresh rate in seconds
    
    light_over_time = [ 
            { "red": 1,  "green": 0, "white": 0 },  # minute 1
            { "red": 3,  "green": 0, "white": 0 },  # minute 2
            { "red": 5,  "green": 0, "white": 0 },  # minute ...
            { "red": 10,  "green": 1, "white": 0 },
            { "red": 15,  "green": 2, "white": 0 },
            { "red": 20,  "green": 4, "white": 0 },
            { "red": 25,  "green": 7, "white": 0 },
            { "red": 30,  "green": 10, "white": 0 },
            { "red": 40,  "green": 14, "white": 0 },
            { "red": 50,  "green": 18, "white": 0 }, # minute 10
            { "red": 50,  "green": 23, "white": 0 },
            { "red": 60,  "green": 30, "white": 0 },
            { "red": 60,  "green": 40, "white": 0 },
            { "red": 70,  "green": 80, "white": 0 },
            { "red": 70,  "green": 80, "white": 1 },
            { "red": 70,  "green": 80, "white": 2 },
            { "red": 70,  "green": 80, "white": 3 },
            { "red": 70,  "green": 80, "white": 5 },
            { "red": 70,  "green": 80, "white": 7 },
            { "red": 70,  "green": 80, "white": 10 }, # minute 20
            { "red": 70,  "green": 80, "white": 14 },
            { "red": 70,  "green": 80, "white": 18 },
            { "red": 70,  "green": 80, "white": 24 },
            { "red": 70,  "green": 80, "white": 30 },
            { "red": 70,  "green": 80, "white": 38 },
            { "red": 70,  "green": 80, "white": 48 },
            { "red": 70,  "green": 80, "white": 60 },
            { "red": 70,  "green": 80, "white": 74 },
            { "red": 70,  "green": 80, "white": 86 },
            { "red": 70,  "green": 80, "white": 100 }, # minute 30
        ]
    
    def __init__(self, lichtwecker):
        BaseLWComponent.__init__(self, lichtwecker)
        self.active = False
        self.alarm = None # will hold the Alarm Object
        
    def start_component_event(self, *args):
        """ start the Alarm Handler
            *args should contain the alarm object and the remaining time 
        """
        
        if (debug): print ("AlarmHandler start event received")

        if (self.active):
            # Handler already active, do not start a new one
            if (debug): print ("AlarmHandler start event dropped (already on)")
            return

        self.alarm = args[0] # double check, if this is the alarm object
    
        if (debug): print ("received alarm at start: {}".format(self.alarm))
    
        # remember the alarm time (so we still know it, when its in the past)
        self.alarmtime = self.alarm.alarmtime()
        
        # Reset snooze
        self.snoozeuntil = None
        
        # Reset audio flag
        self.audioplays = False

        if (debug): self.debug_in_minutes = None

        # set a timer to allow for the ramp up of lighting and starting music
        self.alarmtimer = Timer(self.TIMER_INTERVAL, Event.create("update_alarm_handler"), persist=True).register(self)
        self.displaytimer = Timer(self.DISPLAY_REFRESH_INTERVAL, Event.create("update_display"), persist=True).register(self)
        
        # call handler once on start manually
        self.update_alarm_handler()
        self.update_display()
            
    def keypress(self, key, *args):
        """ 
        Snooze Button is the OK Button. 
        Alarm Button stops Alarm completely.
        """

        if (debug): print ("Key press in AlarmHandler: {}".format(key))

        if (key == self.lw.buttons.okbutton):
            self.snooze()
        
        if (key == self.lw.buttons.alarmbutton):
            # mark alarm as active (Rest was saved during rest of this class
            self.cleanupandend()
            
    def snooze(self):

        # stop music
        self.stopaudio()

        # make it dark
        self.lightsoff()

        # Add snooze interval to current time and store it 
        self.snoozeuntil = datetime.datetime.now() + datetime.timedelta(minutes=self.lw.settings.get("snooze"))

    def cleanupandend(self):
        
        # Dereg Timers
        self.alarmtimer.unregister()
        self.displaytimer.unregister()

        # stop playing audio
        self.stopaudio()

        # light off
        self.lightsoff()

        # reset instance vars
        self.active = False
        
        # back to clock
        self.fire(component_done_event(self))
                
    def update_display(self, *args):

        # Print time (no blinking of the colon this time)
        datetimestring = time.strftime("%H:%M   %d.%m.%y") 
        self.lw.lcd.lcd_string(datetimestring, self.lw.lcd.LCD_LINE_1)
        
        alarm_in_mins = self.alarm_in_minutes()
        
        if (alarm_in_mins <= 0):
            secondline_text = "ALARM, steh auf!"
        else:
            secondline_text = "ALARM in {0:d} min".format(alarm_in_mins)
            
        self.lw.lcd.lcd_string(secondline_text, self.lw.lcd.LCD_LINE_2)
   
    def update_alarm_handler(self, *args):
        """ 
        Controls light and Music
        """
        alarm_in_minutes = self.alarm_in_minutes()
        
        #TODO: Comment out section for production
        # Fast forward alarm to debug, comment out for production mode
        #if (self.debug_in_minutes == None):
        #    self.debug_in_minutes = 30
        #alarm_in_minutes = self.debug_in_minutes
        
        
        if (alarm_in_minutes <= 0):

            if (self.snoozeuntil != None):
                # see if snooze time is over
                snoozetimedelta = self.snoozeuntil - datetime.datetime.now()
                if (snoozetimedelta.total_seconds() < 0):
                    # snooze is over
                    self.snoozeuntil = None

            # Alarm should ring, if not snoozed
            if (self.snoozeuntil == None):
                # It's time to make Alarm!
                
                # Full LIGHTING
                self.lw.led.set_brightness(self.lw.led.RED, 0)
                self.lw.led.set_brightness(self.lw.led.GREEN, 0)
                self.lw.led.set_brightness(self.lw.led.WARM_WHITE, 100)
                
                # Play audio (if not playing already)
                if (self.audioplays == False):
                    self.startaudio()
                        
        elif (alarm_in_minutes > 0 & alarm_in_minutes < 31):
            
            # Light waking should happen
            
            self.lw.led.set_brightness(self.lw.led.RED, self.light_over_time[30-alarm_in_minutes]["red"])
            self.lw.led.set_brightness(self.lw.led.GREEN, self.light_over_time[30-alarm_in_minutes]["green"])
            self.lw.led.set_brightness(self.lw.led.WARM_WHITE, self.light_over_time[30-alarm_in_minutes]["white"])
            
        else:
            # just in case (should not happen)
            self.lightsoff()
            
        
    def startaudio(self):
        music = self.lw.audio.get_titles_info()
        self.lw.audio.playid(music[self.alarm.title_number]["id"])
        self.audioplays = True
            
    def stopaudio(self):
        self.lw.audio.stop() 
        self.audioplays = False
           
    def lightsoff(self):
        self.lw.led.set_brightness(self.lw.led.RED, 0)
        self.lw.led.set_brightness(self.lw.led.GREEN, 0)
        self.lw.led.set_brightness(self.lw.led.WARM_WHITE, 0)
    
    def alarm_in_minutes(self):

        # calc time until alarm in minutes
        alarmdelta = self.alarmtime - datetime.datetime.now()
        alarm_in_mins = int(alarmdelta.total_seconds()/60)

        return alarm_in_mins

class Alarm(object):

        @classmethod
        def from_settings(cls, alarm_num, settings):
            
            minutes = settings.get("alarm_{0:d}_minutes".format(alarm_num))
            hours = settings.get("alarm_{0:d}_hours".format(alarm_num))
            trigger = settings.get("alarm_{0:d}_trigger".format(alarm_num))
            title = settings.get("alarm_{0:d}_title".format(alarm_num))
            with_light = settings.get("alarm_{0:d}_with_light".format(alarm_num))
            is_active = settings.get("alarm_{0:d}_enabled".format(alarm_num))
            
            return Alarm(alarm_hour= hours, alarm_minutes=minutes , alarmtrigger = trigger, with_light = with_light, title_number= title, is_active=("on" is is_active))
    
        def __init__(self, alarm_hour, alarm_minutes, alarmtrigger = "weekdays", with_light = True, title_number = 0, is_active = True):
            
            self.alarmtrigger = alarmtrigger
            self.alarm_hour = alarm_hour
            self.alarm_minutes = alarm_minutes
            self.with_light = with_light
            self.title_number = title_number
            self.is_active = is_active
            
        def __lt__(self, other_alarm):
            
            if (other_alarm.alarm_in_minutes() > self.alarm_in_minutes()):
                return True
            else:
                return False
            
        def __str__(self):
            return ("Alarm: TIME: {0:02d}:{1:02d}, trigger={2:s}".format(self.alarm_hour, self.alarm_minutes, self.alarmtrigger))
            
        def alarmtime(self):
            now = datetime.datetime.now()
            alarm_time = datetime.datetime(now.year, now.month, now.day, self.alarm_hour, self.alarm_minutes)

            
            if (now > alarm_time):
                alarm_time = alarm_time + datetime.timedelta(days=1)

            
            alarm_time = self.add_days_based_on_trigger(alarm_time)

            print ("Alarm_time in alarmtime func: {}".format(alarm_time))

            return alarm_time

        def get_time_as_string(self):
            now = datetime.datetime.now()
            
            print ("alarm in time as string {}".format(self))
            print ("now: {}".format(now))
            print ("alartime: {}".format(self.alarmtime()))
            delta = self.alarmtime() - now
            
            print ("Delta: {}".format(delta.days))  
            
            # locale.setlocale(locale.LC_ALL, 'de.DE')
            
            if (delta.days > 0):
                return ("{0:s} {1:02d}:{2:02d}".format(self.alarmtime().strftime('%a'),self.alarm_hour, self.alarm_minutes))
            else:
                return ("{0:02d}:{1:02d}".format(self.alarm_hour, self.alarm_minutes))
            
            
        def alarm_in_minutes(self):

            now = datetime.datetime.now()
            alarmtime = self.alarmtime()
            
            delta = (alarmtime-now)
            return int(delta.total_seconds()/60)
                                    
        def add_days_based_on_trigger(self, alarmtime):

            
            if ("alldays" == self.alarmtrigger):
                # no need to add a day on daily alarms
                return alarmtime
            
            if ("weekdays" == self.alarmtrigger):
                while (alarmtime.weekday() > 4):
                    alarmtime = alarmtime + datetime.timedelta(days=1)
                return alarmtime
            
            if ("weekend" == self.alarmtrigger):
                print ("in weekend trigger")
                while (alarmtime.weekday() < 5):
                    alarmtime = alarmtime + datetime.timedelta(days=1)
                return alarmtime    
        
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
        if (debug): print ("Initializer of Lichtwecker")

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
        self.alarmhandler = AlarmHandler(self).register(self)
        self.readwlanconfig = ReadWlanConfig(self).register(self)
        

#### EVENT HANDLERS ####

    def started(self, *args):

        # let's start the Lichtwecker with the "boot" state
        self.current_state = "boot"
        #self.current_state = "clock"
        self.fire(start_component_event(), self.current_state)
        if (debug): 
            self.titles = self.audio.get_titles_info()
            print (self.titles)
        
    def component_done_event(self, sender, *args):

        if (len(args) > 0 ):
            if (debug): print ("Component Done: {0:s} Parameter: {1}".format(sender.channel, args[0]))  
        else:
            if (debug): print ("Component Done: {}".format(sender.channel))

        if (sender.channel == "boot"):
            self.start_state("clock")

        if (sender.channel == "clock"):
            target = args[0]
            print ("sender channel = clock, target = {}".format(target))
            if (target == "menu"):
                self.start_state(target)
            if (target =="alarmhandler"):
                self.start_state(target, args[1])

        if (sender.channel == "rereadusb"):
            self.start_state("clock")

        if (sender.channel == "readwlanconfig"):
            self.start_state("clock")
            
        if (sender.channel == "setsnooze"):
            self.start_state("clock")

        if (sender.channel == "setalarm"):
            self.start_state("clock")
            
        if (sender.channel == "alarmhandler"):
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
        if (debug): print ("Button pressed, will send key: {0:d} to : {1:s}".format(key, self.current_state))
        self.fire(keypress(key), self.current_state)
        
    def registered(self, *args):
        if (debug): print ("Registered aus Lichtwecker. Parent: {0:s} -> Child: {1:s}".format(args[1].name, args[0].name))

    def unregistered(self, *args):
        if (debug): print ("Unregistered aus Lichtwecker. Parent: {0:s} -> Child: {1:s}".format(args[1].name, args[0].name))

    def start_state(self, newstate, *args):
        
        if (debug): print ("Starting new state: {}".format(newstate))
        self.current_state = newstate
        if (len(args) > 0):
            self.fire(start_component_event(*args), self.current_state)
        else:
            self.fire(start_component_event(), self.current_state)

        
    def initialize_settings(self):
        
        if (debug): print ("This is Lichtweckers very first start, so we need to populate the settings file")
        self.settings.setsave ("firstrun", False)
        self.settings.setsave ("snooze", 5)
        
        self.settings.setsave ("lcd_brightness", 80)
        
        self.settings.setsave ("alarm_1_enabled",False)
        self.settings.setsave ("alarm_1_title",0)
        self.settings.setsave ("alarm_1_minutes",0)
        self.settings.setsave ("alarm_1_hours",0)
        self.settings.setsave ("alarm_1_trigger", "weekend")
        self.settings.setsave ("alarm_1_with_light", "on")
        
        self.settings.setsave ("alarm_2_enabled",False)
        self.settings.setsave ("alarm_2_title",0)
        self.settings.setsave ("alarm_2_minutes",0)
        self.settings.setsave ("alarm_2_hours",0)
        self.settings.setsave ("alarm_2_trigger", "weekend")
        self.settings.setsave ("alarm_2_with_light", "on")
        
        
        
    """ 

    Überreste

    def on_enter_menu(self):
        self.lcd.lcd_string("SETTINGS:     <>", self.lcd.LCD_LINE_1)
        self.lcd.lcd_string("Alarm 1", self.lcd.LCD_LINE_2)
        
        
    """
