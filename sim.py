# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from __future__ import absolute_import, division, print_function
from itertools import cycle


# a link might have latency
class Link:
   def __init__( self, maxDepth=0 ):
      self.queue = []
      self.maxDepth = maxDepth

   def depth( self ):
      return len( self.queue )
   
   def pop( self ):
      if self.queue:
         return self.queue.pop( 0 )
      return None

   def push( self, message ):
      if self.depth() < self.maxDepth:
         self.queue.append( message )

class Node:
   def __init__( self, name, state=None, links=None, behavior=None ):
      self.name = name
      # links are outgoing
      self.state = state or {}
      # links are essentially the outgoing side of interfaces, keyed by peer 'name'
      self.links = links or {}
      self.behavior = behavior or 'pass'

   def recv( self, message, origin ):
      'handle messages'
      pass

   def runActivities( self ):
      eval( self.behavior )
      return 0

   def hasActivities( self ):
      return False

class Topology:
   def __init__( self ):
      self.nodes = {}
      # key links by [ source ][ sink ]
      self.links = {}

   def step( self ):
      for n in cycle( self.nodes.values() ):
         yield n.runActivities()

if __name__ == "__main__":
   top = Topology()
   top.nodes[ 1 ] = Node( 1 )
   loop = top.step()
   # start in step mode
   cmd = ''
   lastCmd = ''
   while cmd not in ( 'exit', 'quit', 'q' ):
      cmd = input( ':' )
      if not cmd:
         cmd = lastCmd
      if cmd in ( 'c', 'continue' ):
         for _ in loop:
            pass
      elif cmd in ( 'n', 'next', 's', 'step' ):
         next( loop )
      elif cmd in ( 'h', 'help', 'm', 'man' ):
         print( *[
            'usage',
            'c, continue: run continuously',
            'n, next, s, step: run the next step',
            'h, help, m, man: display this help text',
            ], sep='\n' )
      lastCmd = cmd
