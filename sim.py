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
      'behavior is normal code running in runActivities, and can set `remaining`'
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
      remaining = False
      exec( self.behavior )
      return remaining

class Topology:
   def __init__( self ):
      self.nodes = {}
      # key links by [ source ][ sink ]
      self.links = {}
      # track nodes with actions waiting
      self.waiting = set()

   def addNode( self, name, behavior=None ):
      assert name not in self.nodes, 'node names must be unique'
      self.nodes[ name ] = Node( name, behavior=behavior )
      # give node a chance to initialize any awaiting actions
      self.waiting.add( name )

   def step( self ):
      while self.waiting:
         n = self.waiting.pop()
         if self.nodes[ n ].runActivities():
            self.waiting.add( n )
         yield

if __name__ == "__main__":
   top = Topology()
   top.addNode( 1, behavior='print(self.name)' )
   loop = top.step()

   # simple pdb-like interface
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
         if loop:
            next( loop )
         else:
            print( "nothing to do" )
      elif cmd in ( 'h', 'help', 'm', 'man' ):
         print( *[
            'usage',
            'c, continue: run continuously',
            'n, next, s, step: run the next step',
            'h, help, m, man: display this help text',
            ], sep='\n' )
      lastCmd = cmd
