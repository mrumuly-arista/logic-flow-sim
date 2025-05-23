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
            'behaviorName': self.nodeBehavior.get( k, '' ) }
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

      self.links[ name ] = {}
      new_node = Node( name, state=state, txCallback=self.sendCallback )
      self.nodes[ name ] = new_node
      if behaviorName:
         self.setNodeBehavior( name, behaviorName )
      return new_node

   def setNodeBehavior( self, name, behaviorName ):
      assert name in self.nodes, 'no such node'
      if behaviorName:
         assert behaviorName in self.behaviors, 'no such behavior'
      
      behavior = self.behaviors.get( behaviorName, None ) 
      self.nodeBehavior[ name ] = behaviorName or ''

      self.nodes[ name ].behavior = behavior
      # give it a chance to run if it has initialization
      if behaviorName:
         self.waiting.add( name )

   def setNodeState( self, name, key, value ):
      assert name in self.nodes, 'no such node'
      node = self.nodes[ name ]

      if value is None:
         if key in node.state:
            del node.state[ key ]
         return
      node.state[ key ] = value

   def delNode( self, name ):
      if name not in self.nodes:
         # make idempotent
         return
      del self.nodes[ name ]
      # delete all related links
      del self.links[ name ]
      for linkList in self.links.values():
         if name in linkList:
            del linkList[ name ]

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

