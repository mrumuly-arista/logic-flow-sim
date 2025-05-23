# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from __future__ import absolute_import, division, print_function
from cmd import Cmd
from sim import Topology
from simFile import loadTopologyFile, dumpTopology, dumpTopologyFile

# TODO add startup arguments
# -f --file: starting file to load
# -b --batch: batch mode, run non-interactively

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
class SimShell( Cmd ):
   prompt = ':'

   def do_h( self, arg ):
      self.do_help( arg )
   def do_man( self, arg ):
      self.do_help( arg )
   def do_m( self, arg ):
      self.do_help( arg )

   def do_continue( self, arg ):
      if arg:
         return
      for _ in loop:
         pass
   def do_c( self, arg ):
      self.do_continue (arg )

   def do_next( self, arg ):
      iters = int( arg ) if arg else 1
      for i in range( iters ):
         try:
            next( loop )
         except StopIteration:
            print( f'job done in {i} steps' )
            break
   def do_n( self, arg ):
      self.do_next( arg )
   def do_step( self, arg ):
      self.do_next( arg )
   def do_s( self, arg ):
      self.do_next( arg )

   def do_print( self, arg ):
      print( dumpTopology( top ) )
   def do_p( self, arg ):
      self.do_print( arg )
   def do_show( self, arg ):
      self.do_print( arg )

   def do_file( self, arg ):
      if not arg:
         return
      tokens = arg.split()
      if not ( tokens and len( tokens ) > 1 ):
         return
      
      path = " ".join( tokens[ 1: ] )
      if tokens[ 0 ] in ( 'l', 'load' ):
         top = loadTopologyFile( path )
      elif tokens[ 0 ] in ( 'd', 'dump' ):
         dumpTopologyFile( top, path )
   def do_f( self, arg ):
      self.do_file( arg )

   def do_quit( self, arg ):
      if arg:
         return
      return True
   def do_q( self, arg ):
      return self.do_quit( arg )
   def do_exit( self, arg ):
      return self.do_quit( arg )
   def do_e( self, arg ):
      return self.do_quit( arg )
      
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

SimShell().cmdloop()
