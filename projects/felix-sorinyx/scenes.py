# Usable Felix scenes: clip file, start, end (seconds in the screen recording),
# pre-filter (rotation + crop inside the 2096x1180 video area), mood tag.
# Crops are chosen so that no subtitles, logos, watermarks or player UI are visible.
SCENES = {
    # old clips
    "bear":     ("clip2.mov", 0.00, 2.33, "crop=960:960:450:60", "dark"),
    "suit":     ("clip3.mov", 0.00, 4.16, "crop=1000:1000:510:0", "bright"),
    "furwide":  ("clip4.mov", 0.00, 1.80, "crop=940:940:530:0", "pink"),
    "fur":      ("clip4.mov", 2.00, 9.71, "crop=940:940:530:0", "pink"),
    "micsmile": ("clip5.mov", 0.00, 4.21, "transpose=1,crop=1000:1000:160:120", "dark"),
    # clip6: music show stage (green/red), "zoom" logo top-left cropped away
    "stg_blue": ("clip6.mov", 0.05, 0.85, "crop=1020:1020:560:160", "stage"),
    "stg_arm":  ("clip6.mov", 0.92, 1.44, "crop=1020:1020:330:0", "stage"),
    "stg_green":("clip6.mov", 1.68, 2.28, "crop=1020:1020:500:0", "stage"),
    "stg_flip": ("clip6.mov", 3.30, 3.82, "crop=1020:1020:430:0", "stage"),
    "stg_thumb":("clip6.mov", 3.88, 5.25, "crop=1020:1020:650:0", "stage"),
    "stg_red":  ("clip6.mov", 5.32, 9.45, "crop=900:900:600:190", "stage"),
    # clip7
    "blue_up":  ("clip7.mov", 0.05, 3.85, "transpose=1,crop=1040:1040:70:60", "cool"),
    "red_hair": ("clip7.mov", 3.95, 6.18, "crop=1020:1020:470:0", "stage"),
    "red_shy":  ("clip7.mov", 6.25, 7.52, "crop=1020:1020:450:0", "stage"),
    "red_laugh":("clip7.mov", 7.62, 10.85, "crop=1020:1020:530:0", "stage"),
    # clip8: concert, white top + gloves (fancam watermark at the bottom cropped away)
    "glove_mic":("clip8.mov", 0.12, 1.85, "crop=980:980:590:0", "stage"),
    "glove_wide":("clip8.mov", 1.92, 3.57, "crop=980:980:560:0", "stage"),
    "glove_x":  ("clip8.mov", 3.65, 7.68, "crop=980:980:600:0", "stage"),
    # clip9
    "eat":      ("clip9.mov", 0.90, 5.80, "crop=900:900:440:0", "bright"),
    "coffee":   ("clip9.mov", 5.90, 9.65, "crop=980:980:240:0", "cool"),
    "glove_mic2":("clip9.mov", 9.75, 11.42, "crop=980:980:590:0", "stage"),
    # clip10: photoshoot (no overlays)
    "shoot_sit":("clip10.mov", 1.85, 5.62, "crop=1040:1040:500:0", "warm"),
    "shoot_red":("clip10.mov", 5.70, 9.03, "crop=1080:1080:200:0", "warm"),
    "shoot_cam":("clip10.mov", 9.12, 11.55, "crop=1080:1080:20:0", "warm"),
    "brick":    ("clip10.mov", 11.65, 16.10, "crop=920:920:600:0", "warm"),
    # clip12
    "claws":    ("clip12.mov", 0.05, 1.60, "crop=1180:1180:400:0", "dark"),
    "selfie":   ("clip12.mov", 1.70, 8.17, "crop=1080:1080:420:0", "bright"),
    "pink_room":("clip12.mov", 8.26, 11.98, "crop=980:980:420:0", "cool"),
    "pink_up":  ("clip12.mov", 12.08, 15.02, "crop=1000:1000:540:0", "cool"),
    # clip13
    "silver":   ("clip13.mov", 0.05, 4.58, "crop=1060:1060:240:0", "cool"),
    "pink_face":("clip13.mov", 4.68, 7.50, "crop=1000:1000:660:0", "cool"),
    "pink_kiss":("clip13.mov", 7.58, 8.95, "crop=1000:1000:200:0", "cool"),
    "floor":    ("clip13.mov", 10.10, 13.20, "crop=930:930:480:0", "stage"),
    "tank":     ("clip13.mov", 13.62, 14.62, "crop=930:930:460:0", "bright"),
}
BASE = "crop=2096:1180:230:0"
