import queue
import threading
import json
import logging
import asyncio
import websockets
from datetime import datetime

# Global thread-safe event queue
_event_queue = queue.Queue()
# Connected client sockets
_connected_clients = set()

class EventQueue:
    """Centralized thread-safe queue routing business events to WebSocket gateways."""
    _server_started = False
    
    @staticmethod
    def publish_event(event_type: str, payload: dict):
        """Enqueues an event to be broadcast to all connected WebSocket clients."""
        try:
            event = {
                'event_type': event_type,
                'payload': payload,
                'timestamp': datetime.utcnow().isoformat()
            }
            _event_queue.put(event)
            logging.info(f"Published event '{event_type}' to queue.")
        except Exception as e:
            logging.error(f"Error publishing event to queue: {str(e)}")

    @staticmethod
    def start_realtime_server(host: str = '0.0.0.0', port: int = 5001):
        """Starts the WebSocket server and dispatcher in a background thread."""
        if EventQueue._server_started:
            return
        EventQueue._server_started = True
        
        def run_server():
            # Setup a new event loop for this background thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(EventQueue._server_loop(host, port))
            except Exception as ex:
                logging.error(f"WebSocket server runtime exception: {str(ex)}")
            finally:
                loop.close()
            
        t = threading.Thread(target=run_server, daemon=True)
        t.start()
        logging.info(f"Background Real-time server thread started on {host}:{port}")

    @staticmethod
    async def _server_loop(host: str, port: int):
        async def handler(websocket):
            _connected_clients.add(websocket)
            try:
                async for message in websocket:
                    # Client messages (heartbeats, etc.) can be received here
                    pass
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                _connected_clients.discard(websocket)
                
        async with websockets.serve(handler, host, port):
            # Dispatch loop sending messages to clients
            while True:
                await asyncio.sleep(0.1)
                while not _event_queue.empty():
                    event = _event_queue.get()
                    if _connected_clients:
                        message = json.dumps(event)
                        # Dispatch to all clients
                        done, pending = await asyncio.wait(
                            [asyncio.create_task(client.send(message)) for client in _connected_clients],
                            timeout=2.0
                        )
                        # Terminate hung tasks
                        for task in pending:
                            task.cancel()
                        
    @staticmethod
    def get_queue_size() -> int:
        return _event_queue.qsize()
