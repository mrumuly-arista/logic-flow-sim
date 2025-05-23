# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from __future__ import absolute_import, division, print_function
from yaml import safe_load, safe_dump
from sim import Topology

def loadTopology( dump ):
   state = safe_load( dump )
   top = Topology()
   for k, b in state[ 'behaviors' ].items():
      top.addBehavior( str( k ), b )
   for k, n in state[ 'nodes' ].items():
      top.addNode( str( k ), **n )
   for k, l in state[ 'links' ].items():
      src, dst = eval( k )
      src, dst = str( src ), str( dst )
      # each duplex link is created once
      if dst not in top.links.get( src, {} ):
         top.addLink( src, dst )
      # subsequent entries can set maxDepth or messages
      link = top.links[ src ][ dst ]
      link.maxDepth = l[ 'maxDepth' ]
      link.queue = l[ 'queue' ]
   return top

def dumpTopology( topo ):
   state = topo.dump()

   # get block-style for the multiline code strings for easier editing
   bKey = 'behaviors'
   behaviors = { bKey: state[ bKey ] }
   del state[ bKey ]
   
   return safe_dump( behaviors, default_style="|" ) + safe_dump( state )

def loadTopologyFile( path ):
   with open( path, mode='r' ) as file:
      return loadTopology( file )

def dumpTopologyFile( topo, path ):
   with open( path, mode='w' ) as file:
      file.write( dumpTopology( topo ) )
