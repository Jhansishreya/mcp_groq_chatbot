import os
import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import socket
import threading
import json
import time

# Page configuration
st.set_page_config(
    page_title="Groq Chat Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# MCP Server Class
class MCPServer:
    def __init__(self, host='localhost', start_port=5000, max_port_attempts=10):
        self.host = host
        self.start_port = start_port
        self.max_port_attempts = max_port_attempts
        self.port = None
        self.server_socket = None
        self.clients = []
        self.running = False
        self.thread = None

    def start(self):
        for port in range(self.start_port, self.start_port + self.max_port_attempts):
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind((self.host, port))
                self.server_socket.listen(5)
                self.port = port
                self.running = True
                self.thread = threading.Thread(target=self._accept_connections)
                self.thread.daemon = True
                self.thread.start()
                return True
            except socket.error as e:
                if self.server_socket:
                    self.server_socket.close()
                continue
        st.error(f"Failed to start MCP server: Could not find an available port between {self.start_port} and {self.start_port + self.max_port_attempts - 1}")
        return False

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        for client in self.clients:
            client.close()
        self.clients = []
        self.port = None

    def _accept_connections(self):
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                self.clients.append(client_socket)
                client_thread = threading.Thread(target=self._handle_client, args=(client_socket, address))
                client_thread.daemon = True
                client_thread.start()
            except:
                break

    def _handle_client(self, client_socket, address):
        while self.running:
            try:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                message = json.loads(data)
                response = self._process_message(message)
                client_socket.send(json.dumps(response).encode('utf-8'))
            except:
                break
        client_socket.close()
        if client_socket in self.clients:
            self.clients.remove(client_socket)

    def _process_message(self, message):
        return {
            "status": "success",
            "message": "Message received",
            "timestamp": time.time()
        }

# Initialize MCP Server
if 'mcp_server' not in st.session_state:
    st.session_state.mcp_server = MCPServer()

load_dotenv()
groq_api_key = os.getenv('GROQ_API_KEY') or os.getenv('groq_key')

if not groq_api_key:
    st.error("Please set your GROQ_API_KEY environment variable")
    st.stop()

# Sidebar
with st.sidebar:
    st.title('🤖 Groq Chat Settings')
    
    # MCP Server Controls
    st.markdown("---")
    st.subheader('MCP Server')
    
    # Server status
    if st.session_state.mcp_server.running:
        st.success(f"Server Status: ONLINE (Port: {st.session_state.mcp_server.port})")
    else:
        st.error("Server Status: OFFLINE")
    
    # Server controls
    if not st.session_state.mcp_server.running:
        if st.button('Start MCP Server'):
            if st.session_state.mcp_server.start():
                st.success(f"MCP Server started successfully on port {st.session_state.mcp_server.port}!")
                st.experimental_rerun()
    else:
        if st.button('Stop MCP Server'):
            st.session_state.mcp_server.stop()
            st.warning("MCP Server stopped!")
            st.experimental_rerun()
    
    st.markdown("---")
    st.subheader('Chat History')
    if "history" not in st.session_state:
        st.session_state.history = []
    
    for i, entry in enumerate(st.session_state.history):
        if st.button(f'💬 {entry["user"][:30]}...' if len(entry["user"]) > 30 else f'💬 {entry["user"]}', key=f'hist_{i}'):
            st.session_state.current_response = entry["assistant"]

# Main content
st.title('🤖 Groq Chat Assistant')
st.markdown("---")

# Chat input
user_input = st.text_input(
    'Enter your message',
    placeholder="Type your message here...",
    key="user_input"
)

# Set default model
model = "llama3-8b-8192"

# Generate button
if st.button('🚀 Generate Response'):
    if user_input:
        with st.spinner('🤔 Thinking...'):
            try:
                client = Groq(api_key=groq_api_key)
                chat = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "user", "content": user_input}
                    ]
                )
                response = chat.choices[0].message.content
                st.session_state.history.append({"user": user_input, "assistant": response})
                
                # Send response to connected MCP clients
                if st.session_state.mcp_server.running:
                    message = {
                        "type": "chat_response",
                        "user_input": user_input,
                        "response": response,
                        "timestamp": time.time()
                    }
                    for client in st.session_state.mcp_server.clients:
                        try:
                            client.send(json.dumps(message).encode('utf-8'))
                        except:
                            continue
                
                # Display response
                st.info("AI Response:")
                st.write(response)
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
    else:
        st.warning("Please enter a message first!")

# Display current response if exists
if hasattr(st.session_state, 'current_response'):
    st.info("Previous Response:")
    st.write(st.session_state.current_response)
