# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from __future__ import absolute_import, division, print_function

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
      if not self.maxDepth or self.depth() < self.maxDepth:
         self.queue.append( message )
   
   def dump( self ):
      return {
         'maxDepth': self.maxDepth,
         'queue': self.queue,
      }

class Node:
   def __init__( self, name, behavior=None, state=None, txCallback=None ):
      'behavior is normal code running in runActivities, and can set `remaining`'
      self.name = name
      self.behavior = behavior or 'pass'
      self.state = state or {}
      # let the topology know about the transmission
      self.txCallback = txCallback or ( lambda src, dst: None )
      
      # rxlinks are essentially the incoming side of interfaces, keyed by peer name
      self.rxIntfs = {}
      # links are essentially the outgoing side of interfaces, keyed by peer name
      self.txIntfs = {}

      # peer links on which messages are waiting
      self.rxWaiting = set()
      self.remaining = True

   def addLink( self, peer, rx, tx ):
      assert not peer in self.rxIntfs, 'duplicate link'
      self.rxIntfs[ peer ] = rx
      self.txIntfs[ peer ] = tx

   def dump( self ):
      return {
         'name': self.name,
         'behavior': self.behavior,
         'state': self.state
      }

   def recv( self ):
      'get a message from those waiting'
      while self.rxWaiting:
         src = self.rxWaiting.pop()
         link = self.rxIntfs[ src ]
         if not link.depth():
            continue
         msg = link.pop()
         if link.depth():
            self.rxWaiting.add( src )
         return msg
      return None

   def send( self, dst, msg ):
      'send messages'
      assert dst in self.txIntfs, 'no such destination'
      print( f"{self.name} sends {dst}: {msg}")
      self.txIntfs[ dst ].push( msg )
      self.txCallback( self.name, dst )

   def runActivities( self ):
      self.remaining = False
      exec( self.behavior )
      return self.remaining

class Topology:
   def __init__( self ):
      self.nodes = {}
      # key links by [ source ][ sink ]
      self.links = {}
      # behavior blocks for use on nodes
      self.behaviors = {}
      self.nodeBehavior = {}
      # track nodes with actions waiting
      self.waiting = set()

   def dump( self ):
      nodes = { k: n.dump() for k, n in self.nodes.items() }
      state = {
         'behaviors': self.behaviors,
         'nodes': { k: { 
            'state': n[ 'state' ],
            'behaviorName': self.nodeBehavior[ k ] }
            for k, n in nodes.items() },
         'links': {},
      }
      for src, dstList in self.links.items():
         for dst, link in dstList.items():
            state[ 'links' ][ str( ( src, dst ) ) ] = link.dump()
      return state

   def addBehavior( self, name, behavior ):
      self.behaviors[ name ] = behavior
      
   def addNode( self, name, behaviorName=None, state=None ):
      assert name not in self.nodes, 'node names must be unique'
      behavior = self.behaviors.get( behaviorName, None ) 
      if behavior:
         self.nodeBehavior[ name ] = behaviorName

      self.links[ name ] = {}
      new_node = Node( name, behavior=behavior, state=state,
                                 txCallback=self.sendCallback )
      self.nodes[ name ] = new_node
      # give node a chance to initialize any awaiting actions
      self.waiting.add( name )
      return new_node

   def addLink( self, peerA, peerB, maxDepth=0 ):
      assert peerB not in self.links[ peerA ], 'duplicate link'
      ab, ba = Link( maxDepth ), Link( maxDepth )
      self.links[ peerA ][ peerB ] = ab
      self.links[ peerB ][ peerA ] = ba
      self.nodes[ peerA ].addLink( peerB, ba, ab )
      self.nodes[ peerB ].addLink( peerA, ab, ba )

   def sendCallback( self, src, dst ):
      assert dst in self.nodes, 'no such destination'
      self.nodes[ dst ].rxWaiting.add( src )
      self.waiting.add( dst )

   def step( self ):
      while self.waiting:
         n = self.waiting.pop()
         if self.nodes[ n ].runActivities():
            self.waiting.add( n )
         yield

if __name__ == "__main__":
   

   top = Topology()
   bKey = 'hello'
   behavior = '\n'.join( [
      'if not self.state[ "initialized" ]:',
      '   self.send( next( iter( self.txIntfs ) ), "hello wolrd" )',
      '   self.state[ "initialized" ] = True',
      'elif self.rxWaiting:',
      '   print( f"{self.name} got {self.recv()}" )',
      'self.remaining = bool( self.rxWaiting or not self.state[ "initialized" ] )',
   ] )
   top.addBehavior( bKey, behavior )
   top.addNode( 1, behaviorName=bKey, state={ 'initialized': False } )
   top.addNode( 2, behaviorName=bKey, state={ 'initialized': False } )
   top.addLink( 1, 2 )
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
         try:
            next( loop )
         except StopIteration:
            print( 'job done' )
      elif cmd in ( 'h', 'help', 'm', 'man' ):
         print( *[
            'usage',
            'c, continue: run continuously',
            'n, next, s, step: run the next step',
            'h, help, m, man: display this help text',
            'p, print: display state information'
            ], sep='\n' )
      elif cmd in ( 'p', 'print' ):
         # TODO: specify small section to print:
         #    node + name
         #    link + name, name
         #    behavior + name
         from simFile import dumpTopology
         print( dumpTopology( top ) )
      # TODO commands to manipulate topology
      # top/topo/topology
      #    n, node: manipulate node, name
      #       a, add: add node (state and behavior name)
      #       r, remove: remove node (removes associated links as well)
      #       s, set: set state value manually (key, value)
      #       b, behavior: set behavior by name
      #    l, link: manipulate links, name, name
      #       a, add: add link (name, name)
      #       r, remove: remove link (name, name)
      #       m, message: manipulate messages
      #          p, push: push message in
      #          i, insert: add message at specific index
      #          d, drop: remove message at specific index
      # TODO file operations
      # f, file: file tools
      #    l, load: load from file path
      #    d, dump: dump to file path
      lastCmd = cmd
