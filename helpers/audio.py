from mpd import MPDClient, MPDError
import time
import RPi.GPIO as GPIO

class Audio(object):
    
    MUSIC_DIR = "usbstick"
    
    def __init__(self):

        self._mpc = MPDClient()
        self._reconnect()
        self.volume = 95
        
        # fix to remove the crackling noises in the loudspeaker
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(27, GPIO.OUT, initial=GPIO.HIGH)
        
    def set_vol(self, volume):
        self.volume = volume
        self._reconnect()
        self._mpc.setvol(volume)

    def playid(self, songid):
        print ("PlayID: {}".format(songid))
        self._reconnect()
        
        # enable amplifier 
        GPIO.output(27, GPIO.LOW)
        
        self._mpc.playid(songid)
        self._mpc.setvol(self.volume)
        
        
    def playsingle(self, songfile):
        self._reconnect()
        self._mpc.clear()
        self._mpc.add(songfile)

        # enable amplifier 
        GPIO.output(27, GPIO.LOW)

        self._mpc.play()
        self._mpc.setvol(self.volume)

        
    def stop(self):
        self._reconnect()
        self._mpc.stop()

        # disable amplifier 
        GPIO.output(27, GPIO.HIGH)

        
    def refresh_music_dir(self):
        try:
            self._reconnect()
            self._mpc.clear()
            self._mpc.update()
            self._mpc.add(Audio.MUSIC_DIR)
        except MPDError:
            pass

    def get_titles_info(self):
        self._reconnect()
        try:
            playlistid = self._mpc.playlistid()
            return playlistid
        except MPDError:
            return []
    
    def _reconnect(self):
        try:
            self._mpc.connect('localhost','6600')
        except MPDError:
            self._mpc.disconnect()
            self._mpc.connect('localhost','6600')
    

"""
   import time
   from random import choice
   mp = MPDClient()
   # Create the command line parser.
   cli_parser = create_cli_parser()

   # Get the options and arguments.
   opts, args = cli_parser.parse_args(argv)
   # make sure opts.maximum is in a valid range
   if opts.maximum > 100:
      opts.maximum = 100

  def MPDstop():
  try:
      mp.connect('localhost','6600')
  except MPDError:
      mp.disconnect()
      mp.connect('localhost','6600')
  mp.stop()
  if opts.clear:
      mp.clear()
  mp.disconnect()
  return
  def MPDpause(seconds):
  try:
     mp.connect('localhost','6600')
  except MPDError:
     mp.disconnect()
     mp.connect('localhost','6600')
  mp.pause()
  time.sleep(seconds)
  try:
     mp.connect('localhost','6600')
  except MPDError:
     mp.disconnect()
     mp.connect('localhost','6600')
  mp.play()
  mp.disconnect()
  return
  def MPDqueue(songs):
  try:
     mp.connect('localhost','6600')
  except MPDError:
     mp.disconnect()
     mp.connect('localhost','6600')
  mp.setvol(0)
  if opts.artist:
     MPDOption(songs, 'artist')
     else:
        if opts.album:
           MPDOption(songs, 'album')
           else:
              if opts.genre:
                 MPDOption(songs, 'genre')
                 else:
                 while len(mp.playlist()) < songs:
                    for i in range(songs):
                        mp.add(choice(mp.list('file')))
                        mp.play()
  for vol in range(0,opts.maximum+1,opts.step):
     mp.setvol(vol)
    time.sleep(opts.interval)
  mp.disconnect()
  return
  def MPDOption(songs, option):
  try:
     mp.connect('localhost','6600')
  except MPDError:
     mp.disconnect()
     mp.connect('localhost','6600')
  mp.setvol(0)
  opt = choice(mp.list(option))
  while len(mp.playlist()) < songs:
     mp.add(choice(mp.find(option, opt))['file'])
  return

  # define keypress events
  def keypress(event):
  if event.keysym == 'space':
      thread.start_new(MPDpause, (opts.snooze,)) # run in thread
      # to return keypress control immediately to main window
  x = event.char
  if x == 'q' or x == 'Q':
      MPDstop()
  win.destroy()
  #if x == 'p': # for debugging
  # mp.connect('localhost','6600')
  # mp.play()
  # mp.disconnect()
  # if x ==
  # add additional keypress events here 

  # Display the Shell Script output
  win = DisplayScript(opts.window)
  # bind keypress events
  win.bind_all('<Key>', keypress)
  # queue 50 random songs, start playback
  thread.start_new(MPDqueue, (50,)) 

  win.mainloop()
  return
"""