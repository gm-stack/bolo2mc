from struct import pack, unpack, calcsize, error as StructError
from gzip import GzipFile
from UserDict import DictMixin
from StringIO import StringIO
import os, io, math, time, datetime

TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10

class MalformedFileError(Exception):
	"""Exception raised on parse error."""
	pass

class TAG(object):
	"""Each Tag needs to take a file-like object for reading and writing.
	The file object will be initialised by the calling code."""
	id = None

	def __init__(self, value=None, name=None):
		self.name = name
		self.value = value

	#Parsers and Generators
	def _parse_buffer(self, buffer):
		raise NotImplementedError(self.__class__.__name__)

	def _render_buffer(self, buffer, offset=None):
		raise NotImplementedError(self.__class__.__name__)

	#Printing and Formatting of tree
	def tag_info(self):
		return self.__class__.__name__ + \
               ('("%s")'%self.name if self.name else "") + \
               ": " + self.__repr__()

	def pretty_tree(self, indent=0):
		return ("\t"*indent) + self.tag_info()

class _TAG_Numeric(TAG):
	def __init__(self, value=None, name=None, buffer=None):
		super(_TAG_Numeric, self).__init__(value, name)
		self.size = calcsize(self.fmt)
		if buffer:
			self._parse_buffer(buffer)

	#Parsers and Generators
	def _parse_buffer(self, buffer, offset=None):
		self.value = unpack(self.fmt, buffer.read(self.size))[0]

	def _render_buffer(self, buffer, offset=None):
		buffer.write(pack(self.fmt, self.value))

	#Printing and Formatting of tree
	def __repr__(self):
		return str(self.value)

#== Value Tags ==#
class TAG_Byte(_TAG_Numeric):
	id = TAG_BYTE
	fmt = ">b"

class TAG_Short(_TAG_Numeric):
	id = TAG_SHORT
	fmt = ">h"

class TAG_Int(_TAG_Numeric):
	id = TAG_INT
	fmt = ">i"

class TAG_Long(_TAG_Numeric):
	id = TAG_LONG
	fmt = ">q"

class TAG_Float(_TAG_Numeric):
	id = TAG_FLOAT
	fmt = ">f"

class TAG_Double(_TAG_Numeric):
	id = TAG_DOUBLE
	fmt = ">d"

class TAG_Byte_Array(TAG):
	id = TAG_BYTE_ARRAY
	def __init__(self, buffer=None):
		super(TAG_Byte_Array, self).__init__()
		self.value = ''
		if buffer:
			self._parse_buffer(buffer)

	#Parsers and Generators
	def _parse_buffer(self, buffer, offset=None):
		length = TAG_Int(buffer=buffer)
		self.value = buffer.read(length.value)

	def _render_buffer(self, buffer, offset=None):
		length = TAG_Int(len(self.value))
		length._render_buffer(buffer, offset)
		buffer.write(self.value)

	#Printing and Formatting of tree
	def __repr__(self):
		return "[%i bytes]" % len(self.value)

class TAG_String(TAG):
	id = TAG_STRING
	def __init__(self, value=None, name=None, buffer=None):
		super(TAG_String, self).__init__(value, name)
		if buffer:
			self._parse_buffer(buffer)

	#Parsers and Generators
	def _parse_buffer(self, buffer, offset=None):
		length = TAG_Short(buffer=buffer)
		read = buffer.read(length.value)
		if len(read) != length.value:
			raise StructError()
		self.value = unicode(read, "utf-8")

	def _render_buffer(self, buffer, offset=None):
		save_val = self.value.encode("utf-8")
		length = TAG_Short(len(save_val))
		length._render_buffer(buffer, offset)
		buffer.write(save_val)

	#Printing and Formatting of tree
	def __repr__(self):
		return self.value

#== Collection Tags ==#
class TAG_List(TAG):
	id = TAG_LIST
	def __init__(self, type=None, value=None, name=None, buffer=None):
		super(TAG_List, self).__init__(value, name)
		if type:
			self.tagID = type.id
		else: self.tagID = None
		self.tags = []
		if buffer:
			self._parse_buffer(buffer)
		if not self.tagID:
			raise ValueError("No type specified for list")

	#Parsers and Generators
	def _parse_buffer(self, buffer, offset=None):
		self.tagID = TAG_Byte(buffer=buffer).value
		self.tags = []
		length = TAG_Int(buffer=buffer)
		for x in range(length.value):
			self.tags.append(TAGLIST[self.tagID](buffer=buffer))

	def _render_buffer(self, buffer, offset=None):
		TAG_Byte(self.tagID)._render_buffer(buffer, offset)
		length = TAG_Int(len(self.tags))
		length._render_buffer(buffer, offset)
		for i, tag in enumerate(self.tags):
			if tag.id != self.tagID:
				raise ValueError("List element %d(%s) has type %d != container type %d" %
						 (i, tag, tag.id, self.tagID))
			tag._render_buffer(buffer, offset)

	#Printing and Formatting of tree
	def __repr__(self):
		return "%i entries of type %s" % (len(self.tags), TAGLIST[self.tagID].__name__)

	def pretty_tree(self, indent=0):
		output = [super(TAG_List,self).pretty_tree(indent)]
		if len(self.tags):
			output.append(("\t"*indent) + "{")
			output.extend([tag.pretty_tree(indent+1) for tag in self.tags])
			output.append(("\t"*indent) + "}")
		return '\n'.join(output)

class TAG_Compound(TAG, DictMixin):
	id = TAG_COMPOUND
	def __init__(self, buffer=None):
		super(TAG_Compound, self).__init__()
		self.tags = []
		if buffer:
			self._parse_buffer(buffer)

	#Parsers and Generators
	def _parse_buffer(self, buffer, offset=None):
		while True:
			type = TAG_Byte(buffer=buffer)
			if type.value == TAG_END:
				#print "found tag_end"
				break
			else:
				name = TAG_String(buffer=buffer).value
				try:
					#DEBUG print type, name
					tag = TAGLIST[type.value](buffer=buffer)
					tag.name = name
					self.tags.append(tag)
				except KeyError:
					raise ValueError("Unrecognised tag type")

	def _render_buffer(self, buffer, offset=None):
		for tag in self.tags:
			TAG_Byte(tag.id)._render_buffer(buffer, offset)
			TAG_String(tag.name)._render_buffer(buffer, offset)
			tag._render_buffer(buffer,offset)
		buffer.write('\x00') #write TAG_END

	# Dict compatibility.
	# DictMixin requires at least __getitem__, and for more functionality,
	# __setitem__, __delitem__, and keys.

	def __getitem__(self, key):
		if isinstance(key,int):
			return self.tags[key]
		elif isinstance(key, str):
			for tag in self.tags:
				if tag.name == key:
					return tag
			else:
				raise KeyError("A tag with this name does not exist")
		else:
			raise ValueError("key needs to be either name of tag, or index of tag")

	def __setitem__(self, key, value):
		if isinstance(key, int):
			# Just try it. The proper error will be raised if it doesn't work.
			self.tags[key] = value
		elif isinstance(key, str):
			value.name = key
			for i, tag in enumerate(self.tags):
				if tag.name == key:
					self.tags[i] = value
					return
			self.tags.append(value)

	def __delitem__(self, key):
		if isinstance(key, int):
			self.tags = self.tags[:key] + self.tags[key:]
		elif isinstance(key, str):
			for i, tag in enumerate(self.tags):
				if tag.name == key:
					self.tags = self.tags[:i] + self.tags[i:]
					return
			raise KeyError("A tag with this name does not exist")
		else:
			raise ValueError("key needs to be either name of tag, or index of tag")

	def keys(self):
		return [tag.name for tag in self.tags]


	#Printing and Formatting of tree
	def __repr__(self):
		return '%i Entries' % len(self.tags)

	def pretty_tree(self, indent=0):
		output = [super(TAG_Compound,self).pretty_tree(indent)]
		if len(self.tags):
			output.append(("\t"*indent) + "{")
			output.extend([tag.pretty_tree(indent+1) for tag in self.tags])
			output.append(("\t"*indent) + "}")
		return '\n'.join(output)


TAGLIST = {TAG_BYTE:TAG_Byte, TAG_SHORT:TAG_Short, TAG_INT:TAG_Int, TAG_LONG:TAG_Long, TAG_FLOAT:TAG_Float, TAG_DOUBLE:TAG_Double, TAG_BYTE_ARRAY:TAG_Byte_Array, TAG_STRING:TAG_String, TAG_LIST:TAG_List, TAG_COMPOUND:TAG_Compound}

class NBTFile(TAG_Compound):
	"""Represents an NBT file object"""

	def __init__(self, filename=None, mode=None, buffer=None, fileobj=None):
		super(NBTFile,self).__init__()
		self.__class__.__name__ = "TAG_Compound"
		self.filename = filename
		self.type = TAG_Byte(self.id)
		#make a file object
		if filename:
			self.file = GzipFile(filename, mode)
		elif buffer:
			self.file = buffer
		elif fileobj:
			self.file = GzipFile(fileobj=fileobj)
		else:
			self.file = None
		#parse the file given intitially
		if self.file:
			self.parse_file()
			if filename and 'close' in dir(self.file):
				self.file.close()
			self.file = None

	def parse_file(self, filename=None, buffer=None, fileobj=None):
		if filename:
			self.file = GzipFile(filename, 'rb')
		elif buffer:
			self.file = buffer
		elif fileobj:
			self.file = GzipFile(fileobj=fileobj)
		if self.file:
			try:
				type = TAG_Byte(buffer=self.file)
				if type.value == self.id:
					name = TAG_String(buffer=self.file).value
					self._parse_buffer(self.file)
					self.name = name
					self.file.close()
				else:
					raise MalformedFileError("First record is not a Compound Tag")
			except StructError as e:
				raise MalformedFileError("Partial File Parse: file possibly truncated.")
		else: ValueError("need a file!")

	def write_file(self, filename=None, buffer=None, fileobj=None):
		if buffer:
			self.file = buffer
		elif filename:
			self.filename = filename
			self.file = GzipFile(filename, "wb")
		elif fileobj:
			self.file = GzipFile(fileobj=fileobj)
		elif self.filename:
			self.file = GzipFile(self.filename, "wb")
		elif not self.file:
			raise ValueError("Need to specify either a filename or a file")
		#Render tree to file
		TAG_Byte(self.id)._render_buffer(self.file)
		TAG_String(self.name)._render_buffer(self.file)
		self._render_buffer(self.file)
		#make sure the file is complete
		if 'flush' in dir(self.file): 
			self.file.flush()
		if self.filename and 'close' in dir(self.file): 
			self.file.close()

### WARNING! NOT EXTENSIVELY TESTED! ###
class RegionFile(object):
	"""A convenience class for extracting NBT files from the new minecraft Region Format"""
	
	def __init__(self, filename=None, fileobj=None):
		if filename:
			self.filename = filename
			self.file = open(filename, 'rb')
		if fileobj:
			self.file = fileobj
		self.chunks = []
		self.extents = None
		if self.file:
			self.parse_header()

	def __del__(self):
		if self.file:
			self.file.close()

	@classmethod
	def getchunk(path, x, z):
		pass
		
	def get_timestamp(self, x, z):
		self.file.seek(4096+4*(x+z*32))
		timestamp = unpack(">I",self.file.read(4))

	def get_chunk(self, x, z):
		#read metadata block
		block = 4*(x+z*32)
		self.file.seek(block)
		offset, length = unpack(">IB", "\0"+self.file.read(4))
		if offset:
			self.file.seek(offset)
			return NBTFile(fileobj=self.file)
		else:
			return None
	
	def write_chunk(self, x, z, nbt_file):
		""" A smart chunk writer that uses extents to trade off between fragmentation and cpu time"""
		data = StringIO()
		data.seek(0)
		nbtfile.write_file(fileobj = data) #render to buffer
		nsectors = int(math.ceil(data.len/4096))
		
		#if it will fit back in it's orriginal slot:
		self.file.seek(4*(x+z*32))
		offset, length = unpack(">IB", "\0"+self.file.read(4))
		if nsectors <= length:
			sector = offset
		
		#traverse extents to find first-fit
		else:
			sector= 2 #start at sector 2, first sector after header
			while 1:
				#check if extent is used, else move foward in extent list by extent length
				self.file.seek(0)
				found = True
				for intersect_offset, intersect_len in ( (extent_offset, extent_len)
									for extent_offset, extent_len 
									in (unpack(">IB", "\0"+self.file.read(4)) for block in xrange(1024))
									if extent_offset != 0 and ( sector >= extent_offset < (sector+nsectors))):
					#move foward to end of intersect
					sector = intersect_offset + intersect_len
					found = False
					break
				if found:
					break
		
		#write out chunk to region
		self.file.seek(sector*4096)
		self.file.write(pack(">I", (data.len,))) #length field
		self.dile.write(data.getvalue()) #compressed data
		
		#seek to header record and write offset and length records
		self.file.seek(4*(x+z*32))
		self.file.write(pack(">IB", (sector, length))[1:])
		
		#write timestamp
		self.file.seek(4096+4*(x+z*32))
		timestamp = time.mktime(datetime.datetime.now().timetuple())
		self.file.write(pack(">I", (timestamp,)))

