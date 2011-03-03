#!/usr/bin/env python2.7
import bmapparse,sys
mapinfo = bmapparse.parseMapFile('Everard Island.map')

btypes="X~*O+%rGxB"

mapdata = mapinfo['mapdata']

for y in xrange(256):
	for x in xrange(256):
		if (x,y) in mapdata:
			sys.stdout.write(btypes[mapdata[(x,y)]])
		else:
			sys.stdout.write(" ")
	sys.stdout.write("\n")