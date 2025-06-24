import asyncio
import websockets
import pyautogui
import json
import base64
from mss import mss
from PIL import Image, ImageDraw
from io import BytesIO
from collections import deque

PASSWORD = "supersecret"  # Твой пароль
monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
event_queue = deque()

def draw_cursor(image):
    draw = ImageDraw.Draw(image)
    x, y = pyautogui.position()
    if 0 <= x < monitor["width"] and 0 <= y < monitor["height"]:
        size = 6
        draw.line((x - size, y, x + size, y), fill="white", width=2)
        draw.line((x, y - size, x, y + size), fill="white", width=2)

async def send_screen(websocket):
    with mss() as sct:
        while True:
            try:
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                draw_cursor(img)

                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=60)
                img_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
                await websocket.send(json.dumps({"type": "screen", "data": img_data}))
            except Exception as e:
                print("[-] Ошибка отправки изображения:", e)
                break

            # Обработка очереди команд
            if event_queue:
                cmd, val = event_queue.popleft()
                try:
                    if cmd == "click":
                        pyautogui.click(*val)
                    elif cmd == "right_click":
                        pyautogui.rightClick(*val)
                    elif cmd == "move":
                        pyautogui.moveTo(*val)
                    elif cmd == "type":
                        pyautogui.write(val)
                    elif cmd == "scroll":
                        pyautogui.scroll(val)
                    elif cmd == "backspace":
                        pyautogui.press("backspace")
                except Exception as e:
                    print("[-] Ошибка выполнения команды:", e)

            await asyncio.sleep(0.1)

async def handle_client(websocket):
    print("[+] Клиент подключен")
    authorized = False
    screen_task = None

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except Exception:
                continue

            if not authorized:
                if data.get("type") == "auth" and data.get("password") == PASSWORD:
                    authorized = True
                    await websocket.send(json.dumps({"type": "auth", "status": "ok"}))
                    screen_task = asyncio.create_task(send_screen(websocket))
                    print("[+] Клиент авторизован")
                else:
                    await websocket.send(json.dumps({"type": "auth", "status": "fail"}))
                continue

            t = data.get("type")
            if t == "click":
                x, y = int(data.get("x", 0)), int(data.get("y", 0))
                event_queue.append(("click", (x, y)))
            elif t == "right_click":
                x, y = int(data.get("x", 0)), int(data.get("y", 0))
                event_queue.append(("right_click", (x, y)))
            elif t == "move":
                x, y = int(data.get("x", 0)), int(data.get("y", 0))
                event_queue.append(("move", (x, y)))
            elif t == "type":
                text = str(data.get("text", ""))
                event_queue.append(("type", text))
            elif t == "scroll":
                dy = int(data.get("dy", 0))
                event_queue.append(("scroll", dy))
            elif t == "backspace":
                event_queue.append(("backspace", None))

    except Exception as e:
        print("[-] Ошибка соединения:", e)
    finally:
        if screen_task:
            screen_task.cancel()
        print("[-] Клиент отключен")

async def main():
    print("[*] Сервер слушает ws://0.0.0.0:8765")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())
