import struct

def parseMapFile(filename):
	data = open("Everard Island.map",'rb')
	
	def unpackit(string, source):
		size = struct.calcsize(string)
		data = source.read(size)
		return struct.unpack(string,data)
	
	def nibblesplit(instr):
		out = ""
		for c in instr:
			c = ord(c)
			msb = (c & 0xF0) >> 4
			lsb = (c & 0x0F)
			out += (chr(msb) + chr(lsb))
		return out
	
	ftype,version,p,b,s  = unpackit(">8sBBBB",data)
	
	pillboxes = []
	for i in xrange(p):
		x,y,owner,armour,speed = unpackit(">BBBBB",data)
		pb = {
			'x': x,
			'y': y,
			'owner': owner,
			'armour': armour,
			'speed': speed,
		}
		pillboxes.append(pb)
	
	bases = []
	for i in xrange(b):
		x,y,owner,armour,shells,mines = unpackit(">BBBBBB",data)
		base = {
			'x': x,
			'y': y,
			'owner': owner,
			'armour': armour,
			'shells': shells,
			'mines': mines,
		}
		bases.append(base)
	
	startsq = []
	for i in xrange(s):
		x,y,direc = unpackit(">BBB",data)
		square =  {
			'x': x,
			'y': y,
			'direc': direc,
		}
		startsq.append(square)
	
	mapruns = []
	while(1):
		datalen,y,startx,endx = unpackit(">BBBB",data)
		if (y == 255): # end of map
			break
		rundata = data.read(datalen-4)
		rundata = nibblesplit(rundata)
		run = {
			'y': y,
			'startx': startx,
			'endx': endx,
			'data': rundata,
		}
		mapruns.append(run)
	
	mapdata = {}
	
	def setSquare(x,y,t,mapdata):
		mapdata[(x,y)] = t
	
	for maprun in mapruns:
		x = maprun['startx']
		nibblepos = 0
		while(x < maprun['endx']):
			length = ord(maprun['data'][nibblepos])
			nibblepos += 1
			if (length < 8):
				for i in xrange(length+1):
					setSquare(x,maprun['y'],ord(maprun['data'][nibblepos]),mapdata)
					nibblepos += 1
					x += 1
			else:
				length -= 6
				square = ord(maprun['data'][nibblepos])
				nibblepos += 1
				for i in xrange(length):
					setSquare(x,maprun['y'],square,mapdata)
					x += 1
	return { 	'pillboxes': pillboxes, 
				'bases': bases,
				'startsquares': startsq,
				'mapdata': mapdata,
	}