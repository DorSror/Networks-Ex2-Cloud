import sys, socket, os, time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class Handler(FileSystemEventHandler): # event handler class used to check and store relevant events on the monitored directory
	def __init__(self): # initiates a handler object and sets a list of events
		self.events = [] # will hold all the events in a proper order
		self.creations = [] # will hold all creation events, will be the first in order
		self.moves = [] # will hold all move events, will be the second in order
		self.modifies = [] # will hold all modify events, will be the third in order
		self.deletions = [] # will hold all delete events, will be the last in order
	
	def merge_events(self):
		for creation in self.creations:
			self.events.append(creation)
		for move in self.moves:
			self.events.append(move)
		for modify in self.modifies:
			self.events.append(modify)
		for deletion in self.deletions:
			self.events.append(deletion)
		self.creations = []
		self.moves = []
		self.modifies = []
		self.deletions = []
	
	def on_created(self, event): # method that is called when a new file/directory is created
		is_dir_or_file = 'File'
		if os.path.isdir(event.src_path):
			is_dir_or_file = 'Directory'
		event_info = ('Created ' + is_dir_or_file, event.src_path)
		self.creations.append(event_info) # append the creation event
	
	def on_deleted(self, event): # method that is called when a file/directory is deleted
		event_info = ('Deleted', event.src_path)
		self.deletions.append(event_info) # append the deletion event
	
	def on_moved(self, event): # method that is called when a file/directory is moved somewhere else
		event_info = ('Moved', event.src_path, event.dest_path)
		temp_modifies = [] # create a temporary list to hold all modifies
		for modify in self.modifies: # for modify event
			if modify[1] == event.src_path: # if the source path of current move event matches the modify path
				temp_modifies.append(('Modified', event.dest_path)) # append to the temporary list a tweaked version of the modify event
			else:
				temp_modifiers.append(modify) # append the original modify event
		self.modifies = temp_modifies
		self.moves.append(event_info) # append the move event
	
	def on_modified(self, event): # method that is called when a new file/directory is modified
		if os.path.isfile(event.src_path): # note that we don't care about modifications for directories
			event_info = ('Modified', event.src_path)
			self.modifies.append(event_info) # append the modify event

def check_argv(): # checks the arguments and quits if they are not valid, return identifier or None if no identifier
	if not len(sys.argv) in range(5, 7):
		quit()
	if len(sys.argv[1].split('.')) != 4: # checks if first argument is an IP address
		quit()
	if not int(sys.argv[2]) in range(0, 65536): # checks if second argument is in port range
		quit()
	if not sys.argv[4].isdigit(): # check if fourth argument is a digit
		quit()
	if len(sys.argv) == 6: # check if there is an identifier
		# check if identifier has length 128 and is made of letters and numbers
		if not (len(sys.argv[5]) == 128 and sys.argv[5].isalnum() and sys.argv[5].isascii()):
			quit()
		return sys.argv[5]
	return None

def prefix(message): # adds the length of the message at the start of the message (4 digits)
	message_len_str = str(len(message.decode('utf_8')))
	while len(message_len_str) < 4:
		message_len_str = '0' + message_len_str
	return (message_len_str + message.decode('utf_8')).encode('utf_8')

def download_into_dir(client, dir_path, server_dir_path): # recursive method to create files/dirs in given dir_path, and download contents into them
	entries_list_len = int(client.recv(4).decode('utf_8'))
	entries_list = client.recv(entries_list_len).decode('utf_8').replace('\'', '').split(', ') # server sends list of entries in dir
	for entry in entries_list:
		if entry == '': # if the directory is empty, return
			return
		if '.' in entry: # if entry is a file
			f = open(dir_path + '/' + entry, 'wb') # create file with name of entry in the matching client location, write binary
			data_len = 4092
			data = ''
			while data_len == 4092:
				data_len = int(client.recv(4).decode('utf_8'))
				data = client.recv(data_len)
				f.write(data)
			f.close()
		else: # if entry is a directory
			new_dir = dir_path + '/' + entry
			os.mkdir(new_dir) # create dir with name of entry in the matching client location
			download_into_dir(client, new_dir, server_dir_path) # download into new directory

def upload_to_server(client, current_dir): # recursive method to upload files/dirs to the server and their contents
	current_dir_list = os.listdir(current_dir) # list of entries in current dir
	client.send(prefix(str(current_dir_list)[1:-1].encode('utf_8'))) # send list of entries in dir
	for entry in current_dir_list:
		if '.' in entry: # if entry is a file
			f = open(current_dir + '/' + entry, 'rb') # open entry file, read binary
			data_read = f.read(4092)
			while data_read != b'':
				client.send(prefix(data_read))
				data_read = f.read(4092)
			client.send(prefix(b'')) # notify the file transfer has ended
			f.close()
		else: # if entry is a directory
			new_current_dir = current_dir + '/' + entry
			upload_to_server(client, new_current_dir) # upload directory

def create_dir_on_server(client, dir_path): # method used to create a new directory on the server in the case of a new client
	client.send(prefix(b'')) # notify the server there is no identifier
	new_identifier = client.recv(128).decode('utf_8') # get identifier and return
	dir_len = int(client.recv(4).decode('utf_8')) # get length of path
	dir_path_on_server = client.recv(dir_len).decode('utf_8') # get dir path on server
	upload_to_server(client, dir_path) # upload contents into the new directory on the server
	return new_identifier, dir_path_on_server

def upload_file_content(client, file_path): # upload file to the server
	if os.path.isfile(file_path):
		f = open(file_path, 'rb') # open file, read binary
		data_read = f.read(4092)
		while data_read != b'': # read file and send data
			client.send(prefix(data_read))
			data_read = f.read(4092)
		client.send(prefix(b'')) # notify the file transfer has ended
		f.close()
	else:
		client.send(prefix(b'')) 

def update_server(client, event_handler, dir_to_monitor, server_dir_path): # update the server with all the relevant file/dir events
	for event in event_handler.events: # for each event in the list of events
		event_on_server = str(event)[1:-1].replace(dir_to_monitor, server_dir_path) # replace the event path(s) to match the server
		client.send(prefix(event_on_server.encode('utf_8'))) # send event details
		if event[0] == 'Modified': # if the event is a modification of a file
			upload_file_content(client, event[1]) # upload the files contents
	client.send(prefix(b'')) # notify the server there are no more events

def download_file_content(client, file_path):
	f = open(file_path, 'wb') # open file, write binary
	data_len = 4092
	data = ''
	while data_len == 4092: # receive data and write to file as long as data is received
		data_len = int(client.recv(4).decode('utf_8'))
		data = client.recv(data_len)
		f.write(data)
	f.close()

def get_updates_from_server(client, dir_to_monitor, server_dir_path): # CHECK LOGIC OF FILE PATH DIFFERENCE FROM CLIENT TO SERVER
	event_len = 0
	event = ' '
	while event != '': # while there are still events
		event_len = int(client.recv(4).decode('utf_8'))
		event = client.recv(event_len).decode('utf_8')
		event_info = event.replace(server_dir_path, dir_to_monitor).split(', ') # replace event path to match server to (this) client and split
		event_info[0] = event_info[0].replace('\'', '')
		if event_info[0] == '':
			return
		if event_info[0] == 'Created File': # if new file then create the file
			f = open(event_info[1].replace('\'', ''), 'wb')
			f.close()
		elif event_info[0] == 'Modified': # if the event is of a modified file:
			download_file_content(client, event_info[1].replace('\'', '')) # (re/)write contents of file into path
		elif event_info[0] == 'Created Directory':
			os.mkdir(event_info[1].replace('\'', '')) # create new directory
		elif event_info[0] == 'Deleted':
			if os.path.isdir(event_info[1].replace('\'', '')): # if path is dir
				os.rmdir(event_info[1].replace('\'', '')) # remove dir in given path
			else:
				os.remove(event_info[1].replace('\'', '')) # remove file in given path
		else:
			os.system(f"mv {event_info[1]} {event_info[2]} 2>/dev/null") # use terminal commands to move file/dir (if warning/error occurs in console just ignore)

if __name__ == '__main__':
	identifier = check_argv()
	server_ip, server_port, dir_path, time_to_sleep = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
	server_dir_path, dir_to_monitor = '', ''
	event_handler, observer = Handler(), Observer()
	client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	
	# initial connection of client to server
	client.connect((server_ip, server_port))
	if identifier != None: # if identifier was given as input
		client.send(prefix(identifier.encode('utf_8'))) # send identifier
		new_dir = os.path.dirname(os.path.abspath(__file__)) + '/' + identifier
		os.mkdir(new_dir) # create a new directory for which we will download the contents on the server
		dir_to_monitor = new_dir # the directory that we will monitor is the one created on the client's computer
		server_dir_path = dir_path # the dir path on the server is the one given to us
		download_into_dir(client, new_dir, server_dir_path) # donwload into the new directory that we created the server's contents
	else: # if no identifier was given
		identifier, server_dir_path = create_dir_on_server(client, dir_path) # get identifier and dir location on server while uploading the directory to the server
		dir_to_monitor = dir_path # the directory that we will monitor is the one given to the server
	client.close()
	
	# observing changes in the client/server
	observer.schedule(event_handler, dir_to_monitor, recursive=True) # set the observer to monitor the dir_to_monitor recursively
	observer.start() # start the observer
	time.sleep(0.01)
	while True: # update and check for updates from server
		time.sleep(time_to_sleep - 0.01) # sleep (subtracting 0.01s to let the observer catch all of the irrelevant events)
		client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		client.connect((server_ip, server_port)) # connect to the server
		client.send(prefix(identifier.encode('utf_8'))) # send identifier
		event_handler.merge_events()
		update_server(client, event_handler, dir_to_monitor, server_dir_path) # send file/dir events to the server
		get_updates_from_server(client, dir_to_monitor, server_dir_path) # get the updates from backups that happened on the server
		client.close() # disconnect from the server
		time.sleep(0.01) # the observer is too slow, therefore we give it some time to catch all updates that the server sent
		event_handler.events = [] # empty the list of events

