# Direct light providers

The shared lighting API combines the existing Twinkly controller with Philips Hue CLIP v2 and Govee LAN UDP. It resolves saved group members against the current inventory and checks the requested capability before sending each command.

Hue pairing uses a user-confirmed certificate fingerprint and keeps the application key in local app data. Govee status reports provide provisional capabilities, and Govee sends are unconfirmed. Provider requests use private LAN addresses, and the app serves the API through Home Assistant ingress.
