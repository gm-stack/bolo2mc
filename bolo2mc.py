#!/usr/bin/env python2.7
import bmapparse,sys
from nbt import *

print "Opening %s" % (sys.argv[1])
mapinfo = bmapparse.parseMapFile(sys.argv[1])
mapdata = mapinfo['mapdata']

blocks = ""
data = ""

for y in xrange(256):
	for x in xrange(256):
		if (x,y) in mapdata:
			blocks += chr(mapdata[(x,y)])
			data += "\x00"
		else:
			blocks += "\x00"
			data += "\x00"
		

# http://www.minecraftwiki.net/wiki/Schematic_File_Format

nbtfile = NBTFile()
nbtfile.name = "Schematic"
nbtfile.tags.append(TAG_Short(name="Width",value=256))
nbtfile.tags.append(TAG_Short(name="Length",value=256))
nbtfile.tags.append(TAG_Short(name="Height",value=1))
nbtfile.tags.append(TAG_String(name="Materials",value="Alpha"))
nbtfile.tags.append(TAG_Byte_Array(name="Blocks",value=blocks))
nbtfile.tags.append(TAG_Byte_Array(name="Data",value=data))

entlist = TAG_List(name="Entities", type=TAG_Long)
nbtfile.tags.append(entlist)

entlist = TAG_List(name="TileEntities", type=TAG_Long)
nbtfile.tags.append(entlist)

print nbtfile.pretty.tree()

nbtfile.write_file("out.schematic")