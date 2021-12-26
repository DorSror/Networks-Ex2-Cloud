import sys, socket, os, string, random

def check_argv(): # check arguments and quit if not matching the requirements
	if not (sys.argv[1].isdigit() and int(sys.argv[1]) in range(0, 65536)):
		quit()

def prefix(message): # adds the length of the message at the start of the message (4 digits)
	message_len_str = str(len(message.decode('utf_8')))
	while len(message_len_str) < 4:
		message_len_str = '0' + message_len_str
	return (message_len_str + message.decode('utf_8')).encode('utf_8')

def generate_new_identifier(identifiers_dictionary): # create new identifier
	new_identifier = ''.join(random.choices(string.ascii_letters + string.digits, k=128))
	while new_identifier in identifiers_dictionary:
		new_identifier = ''.join(random.choices(string.ascii_letters + string.digits, k=128))
	print(new_identifier)
	return new_identifier

def download_into_dir(client_info, abs_dir_path): # download files into given directory
	entries_list_len = int(client_info[0].recv(4).decode('utf_8'))
	entries_list = client_info[0].recv(entries_list_len).decode('utf_8').replace('\'', '').split(', ') # client sends a list of all entries in directory
	for entry in entries_list:
		if entry == '': # if the directory is empty, return
			return
		if '.' in entry: # if entry is a file
			f = open(abs_dir_path + '/' + entry, 'wb') # create file with name of entry, write binary
			data_len = 4092
			data = ''
			while data_len != 0: # write content into the new file
				data_len = int(client_info[0].recv(4).decode('utf_8'))
				data = client_info[0].recv(data_len)
				f.write(data)
			f.close()
		else: # if entry is a directory
			new_abs_dir_path = abs_dir_path + '/' + entry
			os.mkdir(new_abs_dir_path) # create new directory with name of entry in abs_dir_path
			download_into_dir(client_info, new_abs_dir_path) # download into new directory

def create_new_client(client_info, identifiers_dictionary, client_devices_events): # creates a new client on the server
	new_identifier = generate_new_identifier(identifiers_dictionary) # generates new identifier
	client_info[0].send(new_identifier.encode('utf_8')) # send the new identifier
	identifiers_dictionary[new_identifier] = [] # creates an array of client devices IP for new identifier
	identifiers_dictionary[new_identifier].append(client_info[1][0]) # add the current client's IP address
	client_devices_events[client_info[1][0]] = [] # creates a list of events for an IP
	new_identifier_dir = os.path.dirname(os.path.abspath(__file__)) + '/' + new_identifier # new directory
	client_info[0].send(prefix(new_identifier_dir.encode('utf_8'))) # send the directory location on the server
	os.mkdir(new_identifier_dir)
	download_into_dir(client_info, new_identifier_dir) # download from client the files

def upload_to_client(client_info, current_dir): # upload files to the client
	current_dir_list = os.listdir(current_dir) # list of entries in current dir
	client_info[0].send(prefix(str(current_dir_list)[1:-1].encode('utf_8'))) # send list of entries in dir
	for entry in current_dir_list:
		if '.' in entry: # if entry is a file
			f = open(current_dir + '/' + entry, 'rb') # open entry file, read binary
			data_read = f.read(4092)
			while data_read != b'':
				client_info[0].send(prefix(data_read))
				data_read = f.read(4092)
			client_info[0].send(prefix(b''))
			f.close()
		else: # if entry is a directory
			new_current_dir = current_dir + '/' + entry
			upload_to_client(client_info, new_current_dir) # upload directory

def access_existing_client(client_info, identifiers_dictionary, identifier, client_devices_events):
	identifier_dir = os.path.dirname(os.path.abspath(__file__)) + '/' + identifier
	identifiers_dictionary[identifier].append(client_info[1][0]) # add the current client's IP address to identifiers dictionary
	client_devices_events[client_info[1][0]] = [] # initialize an empty list of events for the device
	upload_to_client(client_info, identifier_dir)

def download_file_content(client_info, file_path):
	f = open(file_path, 'wb') # open file, write binary
	data_len = 4092
	data = ''
	while data_len != 0: # receive data and write to file as long as data is received
		data_len = int(client_info[0].recv(4).decode('utf_8'))
		data = client_info[0].recv(data_len)
		f.write(data)
	f.close()

def update_rest_of_clients_devices(client_info, identifiers_dictionary, identifier, event, client_devices_events): # add the new event to all other client's devices
	for client_device in identifiers_dictionary[identifier]:
		if client_device != client_info[1][0]: # if the devices have a different IP address
			client_devices_events[client_device].append(event) # append the event to the end of the array of relevant events

def synchronize_server_to_client(client_info, identifiers_dictionary, identifier, client_devices_events): # updates files on server according to client
	event_len = int(client_info[0].recv(4).decode('utf_8'))
	event = client_info[0].recv(event_len).decode('utf_8')
	while event != '': # while there are still events
		event_info = event.split(', ') # split event information
		event_info[0] = event_info[0].replace('\'', '')
		if event_info[0] == 'Created File':
			f = open(event_info[1].replace('\'', ''), 'wb')
			f.close()
		elif event_info[0] == 'Modified': # if the event is of a modified
			download_file_content(client_info, event_info[1].replace('\'', '')) # (re/)write contents of file into path
		elif event_info[0] == 'Created Directory':
			os.mkdir(event_info[1].replace('\'', '')) # create new directory
		elif event_info[0] == 'Deleted':
			if os.path.isdir(event_info[1].replace('\'', '')): # if path is dir
				os.rmdir(event_info[1].replace('\'', '')) # remove dir in given path
			else:
				os.remove(event_info[1].replace('\'', '')) # remove file in given path
		else:
			os.system(f"mv {event_info[1]} {event_info[2]} 2>/dev/null") # use terminal commands to move file/dir (if warning/error occurs in console just ignore)
		update_rest_of_clients_devices(client_info, identifiers_dictionary, identifier, event, client_devices_events)
		event_len = int(client_info[0].recv(4).decode('utf_8'))
		event = client_info[0].recv(event_len).decode('utf_8')

def upload_file_content(client_info, file_path): # upload file to the client
	if os.path.isfile(file_path):
		f = open(file_path, 'rb') # open file, read binary
		data_read = f.read(4096)
		while data_read != b'': # read file and send data
			client_info[0].send(data_read)
			data_read = f.read(4096)
		client_info[0].send(prefix(b'')) # notify the client the file has done uploading
		f.close()
	else:
		client_info[0].send(prefix(b'')) # notify the client the file is empty

def update_client(client_info, list_of_events): # update the client with all the relevant events
	for event in list_of_events:
		prefixed = prefix(event.encode('utf_8'))
		client_info[0].send(prefix(event.encode('utf_8'))) # send event info
		event_info = event.split(', ')
		if event_info[0] == 'Modified':
			upload_file_content(client_info, event_info[1]) # upload the files contents
	client_info[0].send(prefix(b'')) # notify the server there are no more events

def synchronize_client_to_server(client_info, identifiers_dictionary, identifier, client_devices_events):
	update_client(client_info, client_devices_events[client_info[1][0]]) # update the client with the list of events
	client_devices_events[client_info[1][0]] = []

if __name__ == '__main__':
	check_argv()
	server_port = int(sys.argv[1])
	server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server.bind(('', server_port))
	identifiers_dictionary = {} # dictionary that matches identifiers to set of IP addresses
	client_devices_events = {} # dictionary that matches and IP address to a list of events
	server.listen(5)
	while True:
		client_socket, client_address = server.accept()
		identifier_len = int(client_socket.recv(4).decode('utf_8'))
		identifier = client_socket.recv(identifier_len).decode('utf_8')
		client_info = (client_socket, client_address)
		if identifier_len == 0: # if new client
			create_new_client(client_info, identifiers_dictionary, client_devices_events) # create new client
		elif not client_address[0] in identifiers_dictionary[identifier]: # else if new computer of old client
			access_existing_client(client_info, identifiers_dictionary, identifier, client_devices_events) # access existing client
		else: # if existing client from known computer
			synchronize_server_to_client(client_info, identifiers_dictionary, identifier, client_devices_events) # synchronizes changes that were done on the client to the server
			synchronize_client_to_server(client_info, identifiers_dictionary, identifier, client_devices_events) # synchronizes changes that were done on the server to the client
		client_socket.close()

