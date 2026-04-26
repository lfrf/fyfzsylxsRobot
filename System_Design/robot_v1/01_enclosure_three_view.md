# Desktop Robot V1 - Enclosure Three-View Draft

## 1. Scope
- Product type: fixed desktop companion robot (no mobile chassis in V1).
- Main interaction: voice + eyes (dual OLED) + head motion (2 DOF).
- Compute strategy: Raspberry Pi on robot, heavy inference on remote server.

## 2. Mechanical Targets
- Total height: 240 mm
- Overall footprint: 140 mm x 140 mm
- Estimated weight: 1.1 kg to 1.6 kg
- Center of mass target: lower than 50 mm above base bottom plane

## 3. Module Placement (by vertical layer)
1. Head shell
- Left OLED eye module
- Right OLED eye module
- USB camera (center)
- Optional microphone board (front lower edge)

2. Neck and gimbal
- Pan servo (yaw, bottom)
- Tilt servo (pitch, upper)
- Servo bracket (aluminum or 3D printed reinforced PETG)

3. Base upper layer
- Raspberry Pi 5 + active cooler
- I2C distribution board
- USB audio adapter (if needed)

4. Base middle layer
- PCA9685 servo driver
- Audio amplifier board
- Main wiring harness and ferrite sleeves

5. Base lower layer
- 12V input jack
- 5V buck converter for Pi
- 6V buck converter for servos
- Fuse + rocker switch
- Steel ballast plate

## 4. Three-View Dimensions

### 4.1 Front View
```
        <----------- 120 ----------->
        +---------------------------+  ^
        |   [ OLED-L ] [ OLED-R ]   |  | 80 (head)
        |            CAM            |  v
        +---------------------------+
                 ||  neck  ||
              +----------------+      ^
              |      base      |      | 60 (base)
              +----------------+      v
              <------ 140 ------>

Total height: 240
```

### 4.2 Side View
```
          <------ 90 ------>
          +---------------+    ^
          |    head body  |    | 80
          +---------------+    v
                ||
              (gimbal)
          +---------------+    ^
          |      base     |    | 60
          +---------------+    v
          <------ 140 ----->

Total height: 240
```

### 4.3 Top View
```
           +-----------------------+
           |     front panel       |
           |   OLED-L   CAM  OLED-R|
           |                       |
           |     head outline      |
           +-----------------------+
                  120 x 90

   Base outline: 140 x 140
```

## 5. Fastener and Print Guidelines
- Base and head shell: PETG 2.4 mm wall, 25% infill.
- Servo bracket: PETG/nylon, 4 perimeter walls, 40% infill.
- Screws:
  - M2.5 for Raspberry Pi
  - M3 for shell joins and bracket
- Use heat-set inserts for repeated maintenance openings.

## 6. Thermal and EMI Notes
- Keep Pi fan intake clear on base top.
- Route servo power wires away from camera data line.
- Keep amplifier board at least 15 mm away from buck converters.
