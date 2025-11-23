/*
 * ESP8266 Wii Nunchuk Game Controller (Headless/Serial Version)
 * 
 * Protocol: WebSockets (Port 81)
 * Wiring: 
 *   - Nunchuk SDA -> NodeMCU D2 (GPIO 4)
 *   - Nunchuk SCL -> NodeMCU D1 (GPIO 5)
 *   - VCC -> 3.3V
 *   - GND -> GND
 */

#include <ESP8266WiFi.h>
#include <WebSocketsServer.h> //Works with V2.3.3 https://www.google.com/url?sa=E&q=https%3A%2F%2Fgithub.com%2FLinks2004%2FarduinoWebSockets%2Freleases
#include <NintendoExtensionCtrl.h>

// --- CONFIGURATION ---
const char* ssid = "your-ssid-name";      // <--- CHANGE THIS
const char* password = "your-ssid-password"; // <--- CHANGE THIS

// --- OBJECTS ---
WebSocketsServer webSocket = WebSocketsServer(81);
Nunchuk nchuk;

// --- STATE VARIABLES ---
unsigned long lastFrameTime = 0;
const int targetFrameRate = 60; // 60Hz updates
bool clientConnected = false;

// Connection tracking
bool nunchukFound = false; 
unsigned long lastReconnectAttempt = 0;

void setup() {
  Serial.begin(115200);
  delay(100); 
  Serial.println();
  Serial.println("--- ESP8266 Nunchuk Controller Starting ---");

  // 1. Connect to WiFi
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.println("WiFi Connected!");
  Serial.print("Server IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.println("Enter this IP in the game prompt.");

  // 2. Initialize Nunchuk
  nchuk.begin(); 
  
  if (nchuk.connect()) {
    nunchukFound = true;
    Serial.println("Nunchuk: CONNECTED successfully.");
  } else {
    nunchukFound = false;
    Serial.println("Nunchuk: NOT DETECTED (Will keep retrying...)");
  }

  // 3. Start WebSocket Server
  webSocket.begin();
  webSocket.onEvent(webSocketEvent);
  Serial.println("WebSocket Server started on Port 81");
}

void loop() {
  webSocket.loop();
  
  // 1. Handle Nunchuk Connection / Reconnection
  bool success = nchuk.update();

  if (success) {
    if (!nunchukFound) {
      Serial.println("Nunchuk: RECONNECTED!");
      nunchukFound = true;
    }
  } else {
    if (nunchukFound) {
      Serial.println("Nunchuk: DISCONNECTED / READ ERROR");
      nunchukFound = false;
    }
    
    // Retry connection every 1 second
    if (millis() - lastReconnectAttempt > 1000) {
      lastReconnectAttempt = millis();
      Serial.println("Attempting to connect to Nunchuk...");
      if(nchuk.connect()) {
        // Wait for next update() to confirm success
      }
    }
  }

  // 2. Send Data (Only if Nunchuk works AND Client is connected)
  if (nunchukFound && clientConnected) {
    unsigned long currentMillis = millis();
    if (currentMillis - lastFrameTime >= (1000 / targetFrameRate)) {
      lastFrameTime = currentMillis;
      sendControllerData();
    }
  }
}

void sendControllerData() {
  // Construct JSON manually. 
  // We split this up to avoid C++ string concatenation errors.
  
  String json = "{";
  json += "\"jx\":" + String(nchuk.joyX()) + ",";
  json += "\"jy\":" + String(nchuk.joyY()) + ",";
  json += "\"ax\":" + String(nchuk.accelX()) + ",";
  json += "\"ay\":" + String(nchuk.accelY()) + ",";
  
  // Logic Fix: Append the button parts separately
  json += "\"c\":";
  json += (nchuk.buttonC() ? "1" : "0");
  json += ",";
  
  json += "\"z\":";
  json += (nchuk.buttonZ() ? "1" : "0");
  
  json += "}";

  webSocket.broadcastTXT(json);
}

void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      clientConnected = false;
      Serial.printf("[%u] Browser Client Disconnected!\n", num);
      break;
    case WStype_CONNECTED:
      clientConnected = true;
      IPAddress ip = webSocket.remoteIP(num);
      Serial.printf("[%u] Browser Client Connected from %d.%d.%d.%d\n", num, ip[0], ip[1], ip[2], ip[3]);
      break;
  }
}
