import signal
import socket
import sys
import threading

from bs4 import BeautifulSoup


class ServerSocket:
    def __init__(self, config):
        signal.signal(signal.SIGINT, self.shutdown)
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serverSocket.bind((config['HOST_NAME'], config['BIND_PORT']))
        self.serverSocket.listen(10)
        self.__clients = {}
        i = 0
        while True:
            (clientSocket, client_address) = self.serverSocket.accept()
            d = threading.Thread(name=i, target=self.proxy_thread, args=(clientSocket, client_address))
            i = i + 1
            d.setDaemon(True)
            d.start()

    def shutdown(self, signum, frame):
        main_thread = threading.currentThread()
        for t in threading.enumerate():
            if t is main_thread:
                continue
            t.join()
            self.serverSocket.close()
        sys.exit(0)

    def recv_http(self, socket):
        text_data = b''
        while True:
            next_byte = socket.recv(1)
            text_data += next_byte
            if len(text_data) == 0:
                break
            if chr(text_data[-1]) == '\n' \
                    and chr(text_data[-2]) == '\r' \
                    and chr(text_data[-3]) == '\n' \
                    and chr(text_data[-4]) == '\r':
                lines = text_data.decode('iso-8859-1').split('\r\n')
                status_code = lines[0]
                headers = {}
                for line in lines[1:]:
                    if line != '':
                        line_args = line.split(': ')
                        headers[line_args[0]] = line_args[1]
                data = b''
                if 'Content-Length' in headers.keys():
                    while int(headers['Content-Length']) > len(data):
                        data += socket.recv(int(headers['Content-Length']) - len(data))
                return status_code, headers, data
        raise Exception('None!')

    def proxy_thread(self, clientSocket, client_address):
        request = clientSocket.recv(config['MAX_REQUEST_LEN']).decode()
        if request == '':
            return
        first_line = request.split('\n')[0]
        url = first_line.split(' ')[1]
        http_pos = url.find("://")
        if http_pos == -1:
            temp = url
        else:
            temp = url[(http_pos + 3):]

        port_pos = temp.find(":")
        webserver_pos = temp.find("/")
        if webserver_pos == -1:
            webserver_pos = len(temp)
        webserver = ""
        port = -1
        if port_pos == -1 or webserver_pos < port_pos:
            port = 80
            webserver = temp[:webserver_pos]
        else:
            port = int((temp[(port_pos + 1):])[:webserver_pos - port_pos - 1])
            webserver = temp[:port_pos]

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.settimeout(config['CONNECTION_TIMEOUT'])
        server_socket.connect((webserver, port))
        server_socket.sendall(request.encode())

        status_code, headers, data = self.recv_http(server_socket)
        request = status_code + '\r\n'
        content_length = ''
        for key, val in dict(headers).items():
            if key.lower() == 'content-type':
                if 'text/html' in val.lower():
                    soup = BeautifulSoup(data.decode('utf-8', 'ignore'), 'lxml')
                    with open("block.txt") as file:
                        array = [row.strip() for row in file]
                    for block_str in array:
                        for div in soup.find_all("div", {'class': block_str}):
                            div.decompose()
                        for div in soup.find_all("div", {'id': block_str}):
                            div.decompose()
                        for div in soup.find_all("body", {'class': block_str}):
                            div.decompose()
                        for tr in soup.find_all("tr", {'class': block_str}):
                            tr.decompose()
                    data = str(soup).encode()
                    content_length = str(len(data))
                request += ('%s: %s\r\n' % (key, val))
            if key.lower() == 'content-length':
                if not content_length:
                    content_length = val
            else:
                request += ('%s: %s\r\n' % (key, val))
        request += ('%s: %s\r\n' % ('Content-length', content_length))
        clientSocket.send((request + '\r\n').encode() + data)


if __name__ == '__main__':
    port = 80
    if len(sys.argv) == 2:
        port = int(sys.argv[1])
    config = {
        'HOST_NAME': 'localhost',
        'BIND_PORT': port,
        'MAX_REQUEST_LEN': 1000000,
        'CONNECTION_TIMEOUT': 100,
    }
    server = ServerSocket(config)
