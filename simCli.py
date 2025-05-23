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
loop = top.step()

# simple pdb-like interface
class SimShell( Cmd ):
   prompt = ':'

   def do_h( self, arg ):
      'alias: help'
      self.do_help( arg )
   def do_man( self, arg ):
      'alias: help'
      self.do_help( arg )
   def do_m( self, arg ):
      'alias: help'
      self.do_help( arg )

   def do_continue( self, arg ):
      'next as long as there is activity waiting'
      if arg:
         return
      for _ in loop:
         pass
   def do_c( self, arg ):
      'alias: continue'
      self.do_continue (arg )

   def do_next( self, arg ):
      'perform a number of steps, "next [STEPS=1]"'
      iters = int( arg ) if arg else 1
      for i in range( iters ):
         try:
            next( loop )
         except StopIteration:
            print( f'job done in {i} steps' )
            break
   def do_n( self, arg ):
      'alias: next'
      self.do_next( arg )
   def do_step( self, arg ):
      'alias: next'
      self.do_next( arg )
   def do_s( self, arg ):
      'alias: next'
      self.do_next( arg )

   def do_print( self, arg ):
      'print current state of topology'
      print( dumpTopology( top ) )
   def do_p( self, arg ):
      'alias: print'
      self.do_print( arg )
   def do_show( self, arg ):
      'alias: print'
      self.do_print( arg )
   def do_sh( self, arg ):
      'alias: print'
      self.do_print( arg )

   def do_file( self, arg ):
      'Perform file operations: "file load PATH", "file dump PATH"'
      if not arg:
         return
      tokens = arg.split()
      if not ( tokens and len( tokens ) > 1 ):
         return
      
      path = " ".join( tokens[ 1: ] )
      if tokens[ 0 ] in ( 'l', 'load' ):
         global top, loop
         try:
            top = loadTopologyFile( path )
            loop = top.step()
         except FileNotFoundError:
            print( "file not found" )
      elif tokens[ 0 ] in ( 'd', 'dump' ):
         dumpTopologyFile( top, path )
   def do_f( self, arg ):
      "alias: file"
      self.do_file( arg )

   def do_quit( self, arg ):
      'terminate program'
      if arg:
         return
      return True
   def do_q( self, arg ):
      'alias: quit'
      return self.do_quit( arg )
   def do_exit( self, arg ):
      'alias: quit'
      return self.do_quit( arg )
   def do_e( self, arg ):
      'alias: quit'
      return self.do_quit( arg )

   def do_topology( self, arg ):
      'manipulate the current topology'
      if not arg:
         return
      tokens = arg.split()
      if not tokens:
         return
      
      if tokens[ 0 ] in ( 'n', 'node' ):
         if not len( tokens ) > 2:
            return
         name = tokens[ 1 ]
         op = tokens[ 2 ]
         if op in ( 'a', 'add' ):
            # TODO: optional [BEHAVIOR] [STATE]
            top.addNode( name )
         elif op in ( 'r', 'remove', 'd', 'del', 'delete' ):
            top.delNode( name )
         elif op in ( 's', 'state' ):
            if not len( tokens ) > 3:
               return
            key = tokens[ 3 ]
            value = None if len( tokens ) == 4 else " ".join( tokens[ 4: ] )
            top.setNodeState( name, key, value )
         elif op in ( 'b', 'behavior' ):
            if not len( tokens ) > 3:
               return
            behaviorName = tokens[ 3 ]
            top.setNodeBehavior( name, behaviorName )
         else:
            print( "unknown topology node NAME command" )
      elif tokens[ 0 ] in ( 'l', 'link' ):
         pass
      elif tokens[ 0 ] in ( 'b', 'behavior' ):
         pass
      else:
         print( "unknown topology command" )

   def do_t( self, arg ):
      'alias: topology'
      self.do_topology( arg )
   def do_top( self, arg ):
      'alias: topology'
      self.do_topology( arg )
   def do_topo( self, arg ):
      'alias: topology'
      self.do_topology( arg )
      
   # TODO commands to manipulate topology
   # top/topo/topology
   #    n, node: manipulate node, name
   #       a, add: add node (optional behavior name, state)
   #       r, remove: remove node (removes associated links as well)
   #       s, set: set state value manually (key, value)
   #       b, behavior: set behavior by name
   #    l, link: manipulate links, name, name
   #       a, add: add link
   #       r, remove: remove link
   #       m, message: manipulate messages
   #          p, push: push message in
   #          i, insert: add message at specific index
   #          d, drop: remove message at specific index

SimShell().cmdloop()
