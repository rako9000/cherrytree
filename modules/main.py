#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
#       main.py
#       
#       Copyright 2009-2011 Giuseppe Penone <giuspen@gmail.com>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

import gtk, gobject
import sys, os, gettext, socket, threading
import cons, core

HOST = "127.0.0.1"
PORT = 63891


class ServerThread(threading.Thread):
   """Server listening for requests to open new documents"""
   def __init__(self, semaphore, msg_server_to_core):
      super(ServerThread, self).__init__()
      self.semaphore = semaphore
      self.msg_server_to_core = msg_server_to_core
      self.time_to_quit = False
      
   def run(self):
      sock_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock_srv.bind((HOST, PORT))
      sock_srv.settimeout(2) # 2 sec
      sock_srv.listen(1)
      while not self.time_to_quit:
         try: conn, addr = sock_srv.accept()
         except: continue
         print "connected with", addr
         while not self.time_to_quit:
            data = conn.recv(1024)
            if not data: break
            if len(data) < 4 or data[:4] != "ct*=":
               print "bad data =", data
               break
            conn.send("okz")
            filepath = data[4:]
            if not os.path.dirname(filepath): filepath = os.path.join(os.getcwd(), filepath)
            else: filepath = os.path.abspath(filepath)
            #print filepath
            self.semaphore.acquire()
            self.msg_server_to_core['p'] = filepath
            self.msg_server_to_core['f'] = 1
            self.semaphore.release()
         conn.close()


class CherryTreeHandler():
   def __init__(self, filepath, semaphore, msg_server_to_core, lang_str):
      self.semaphore = semaphore
      self.msg_server_to_core = msg_server_to_core
      self.lang_str = lang_str
      self.running_windows = []
      if not os.path.dirname(filepath): filepath = os.path.join(os.getcwd(), filepath)
      else: filepath = os.path.abspath(filepath)
      self.window_open_new(filepath)
      self.server_check_timer_id = gobject.timeout_add(1000, self.server_periodic_check) # 1 sec
      
   def window_open_new(self, filepath):
      """Open a new top level Window"""
      window = core.CherryTree(self.lang_str, filepath, self)
      self.running_windows.append(window)
      self.curr_win_idx = -1
      
   def on_window_destroy_event(self, widget):
      """Before close the application (from the window top right X)..."""
      self.running_windows.pop(self.curr_win_idx)
      self.curr_win_idx = -1
      if not self.running_windows: gtk.main_quit()
      
   def server_periodic_check(self):
      """Check Whether the server posted messages"""
      self.semaphore.acquire()
      #print "check '%s'" % self.msg_server_to_core['f']
      if self.msg_server_to_core['f']:
         self.msg_server_to_core['f'] = 0
         for i, runn_win in enumerate(self.running_windows):
            if self.msg_server_to_core['p']\
            and runn_win.file_name\
            and self.msg_server_to_core['p'] == os.path.join(runn_win.file_dir, runn_win.file_name):
               print "rise existing '%s'" % self.msg_server_to_core['p']
               self.curr_win_idx = i
               runn_win.window.present()
               break
         else:
            print "run '%s'" % self.msg_server_to_core['p']
            self.window_open_new(self.msg_server_to_core['p'])
      self.semaphore.release()
      return True # this way we keep the timer alive


def initializations():
   """Initializations"""
   if sys.platform[0:3] == "win":
      import warnings
      warnings.filterwarnings("ignore")
   else:
      try:
         # change process name
         import ctypes, ctypes.util
         libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("libc"))
         libc.prctl(15, cons.APP_NAME, 0, 0, 0)
      except: print "libc.prctl not available, the process name will be python and not cherrytree"
   try:
      # change locale text domain
      import locale
      locale.bindtextdomain(cons.APP_NAME, cons.LOCALE_PATH)
   except: print "locale.bindtextdomain not available, the glade i18n may not work properly"
   # language installation
   if os.path.isfile(cons.LANG_PATH):
      lang_file_descriptor = file(cons.LANG_PATH, 'r')
      lang_str = lang_file_descriptor.read()
      lang_file_descriptor.close()
      if lang_str != 'default': os.environ["LANGUAGE"] = lang_str
   else: lang_str = 'default'
   try: gettext.translation(cons.APP_NAME, cons.LOCALE_PATH).install()
   except:
      import __builtin__
      def _(transl_str):
         return transl_str
      __builtin__._ = _
   return lang_str


def main(OPEN_WITH_FILE):
   """Everything Starts from Here"""
   try:
      # client
      sock_cln = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock_cln.connect((HOST, PORT))
      sock_cln.send("ct*=%s" % OPEN_WITH_FILE)
      data = sock_cln.recv(1024)
      sock_cln.close()
      if data != "okz": raise
   except:
      # server + core
      lang_str = initializations()
      gobject.threads_init()
      semaphore = threading.Semaphore()
      msg_server_to_core = {'f':0, 'p':""}
      server_thread = ServerThread(semaphore, msg_server_to_core)
      server_thread.start()
      CherryTreeHandler(OPEN_WITH_FILE, semaphore, msg_server_to_core, lang_str)
      gtk.main() # start the gtk main loop
      # quit thread
      server_thread.time_to_quit = True
      return 0
