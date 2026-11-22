"""
STORMY TWEAKS v1.4-FULL-ULTIMATE-PURPLE
First, once: pip install customtkinter
Then run: python stormy_tweaks_purple.pyw
All tweaks are reversible. Backups are stored in the %APPDATA%\\StormyTweaks folder.
"""
import ctypes, gc, json, os, platform, queue, re, shutil, socket, subprocess, sys, tempfile, threading, time, winreg
import tkinter as tk
import tkinter.font as tkf
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Net (bulanık olmayan) yazı için: Tk penceresi oluşmadan önce DPI farkındalığı
try:
  ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
  try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
  except Exception:
    pass

APP = "Stormy Tweaks"
VER = "v1.4 · FULL ULTIMATE + PURPLE"
DIR = os.path.join(os.environ.get("APPDATA", "."), "StormyTweaks")
os.makedirs(DIR, exist_ok=True)
DATA = os.path.join(DIR, "data.json")

# --- MOR TEMA PALETI ---
BG, SIDE, CARD, BORDER = "#0d0914", "#09060e", "#161022", "#2c1e47"
TXT, MUTED = "#f3e8ff", "#9484b3"
PURPLE, GREEN, RED, DARK = "#7c3aed", "#10b981", "#ef4444", "#1d1530"
DWORD, SZ = winreg.REG_DWORD, winreg.REG_SZ
HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
ULT_PERF = "e9a42b02-d5df-448d-aa00-03f14749eb61"


def gpu_pref(d):
  """DirectX per-app GPU preference (2 = high performance) for every game in the library."""
  return [(r"Software\Microsoft\DirectX\UserGpuPreferences", g.replace("/", "\\"), "GpuPreference=2;", SZ)
      for g in d["games"]]


# ---- Dinamik tweak yardimcilari: sadece bu PC'de GERCEKTEN var olan anahtarlara yazar ----
_VIRT = ("virtual", "hyper-v", "vpn", "bluetooth", "loopback", "miniport", "wintun", "tap-", "vmware",
     "vbox", "tunnel", "pseudo", "wan ")
_CLS_NET = r"HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
_CLS_GPU = r"HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
_SVC = r"HKLM\SYSTEM\CurrentControlSet\Services"


def _subkeys(path):
  out = []
  try:
    root, sub = hk(path)
    with winreg.OpenKey(root, sub) as k:
      i = 0
      while True:
        try:
          out.append(winreg.EnumKey(k, i))
          i += 1
        except OSError:
          break
  except OSError:
    pass
  return out


def _val(path, name):
  r = read_reg(path, name)
  return None if r is None else r[0]


def iface_tcp(d):
  """TcpAckFrequency / TCPNoDelay: sadece IP'si olan aktif arayuzlere."""
  base = r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
  out = []
  for g in _subkeys(base):
    p = base + "\\" + g
    ip = _val(p, "DhcpIPAddress") or _val(p, "IPAddress")
    if isinstance(ip, (list, tuple)):
      ip = next((x for x in ip if x), "")
    if ip and ip != "0.0.0.0":
      out += [(p, "TcpAckFrequency", 1, DWORD), (p, "TCPNoDelay", 1, DWORD), (p, "TcpDelAckTicks", 0, DWORD)]
  return out


def eth_tune(d):
  """Ethernet kartlarinda guc tasarrufu / EEE / interrupt moderation kapat (var olan ayarlara)."""
  keys = ("*EEE", "EnableGreenEthernet", "GigaLite", "*FlowControl", "*InterruptModeration", "EnablePME",
      "AdvancedEEE", "ULPMode", "PowerSavingMode", "EnableSavePowerNow", "EEELinkAdvertisement")
  out = []
  for n in _subkeys(_CLS_NET):
    if not n.isdigit():
      continue
    p = _CLS_NET + "\\" + n
    desc = str(_val(p, "DriverDesc") or "").lower()
    if not desc or any(v in desc for v in _VIRT) or _val(p, "*PhysicalMediaType") != 14:
      continue
    out.append((p, "PnPCapabilities", 24, DWORD))
    for k in keys:
      r = read_reg(p, k)
      if r is not None:
        out.append((p, k, 0 if r[1] == DWORD else "0", r[1]))
  return out


def gpu_nv(d):
  """NVIDIA: sabit yuksek P-State / PowerMizer max performans."""
  out = []
  for n in _subkeys(_CLS_GPU):
    if not n.isdigit():
      continue
    p = _CLS_GPU + "\\" + n
    if "nvidia" not in str(_val(p, "DriverDesc") or "").lower():
      continue
    out += [(p, "DisableDynamicPstate", 1, DWORD), (p, "PerfLevelSrc", 0x2222, DWORD),
        (p, "PowerMizerEnable", 1, DWORD), (p, "PowerMizerLevel", 1, DWORD),
        (p, "PowerMizerLevelAC", 1, DWORD)]
  return out


def msi_mode(d):
  """Ekran karti ve ag karti icin MSI (Message Signaled Interrupts) modu."""
  base = r"HKLM\SYSTEM\CurrentControlSet\Enum\PCI"
  out = []
  for dev in _subkeys(base):
    for inst in _subkeys(base + "\\" + dev):
      p = base + "\\" + dev + "\\" + inst
      if _val(p, "Class") in ("Display", "Net"):
        out.append((p + r"\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties",
              "MSISupported", 1, DWORD))
  return out


def svc_off(*names):
  """Servisleri (Start=4) kapat; sadece bu PC'de var olanlari."""
  def f(d):
    return [(_SVC + "\\" + n, "Start", 4, DWORD) for n in names if read_reg(_SVC + "\\" + n, "Start") is not None]
  return f


TWEAKS = [
  # ==================== GAMING / FPS / INPUT DELAY ( & & FULL) ====================
  dict(id="gamemode", page="tweaks", name="Game Mode",
     desc="Turns on Windows Game Mode to prioritize active games and lower background load.",
     reg=[(r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1, DWORD),
       (r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1, DWORD)]),
  dict(id="dvr", page="tweaks", name="Disable Game DVR & Capture",
     desc="Turns off background game recording & capture to prevent FPS drops and stutter.",
     reg=[(r"System\GameConfigStore", "GameDVR_Enabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "HistoricalCaptureEnabled", 0, DWORD)]),
  dict(id="mouse", page="tweaks", name="Disable Mouse Acceleration (1:1)",
     desc="Turns off mouse acceleration for 1:1 aim consistency. (Sign out/in for full effect)",
     reg=[(r"Control Panel\Mouse", "MouseSpeed", "0", SZ),
       (r"Control Panel\Mouse", "MouseThreshold1", "0", SZ),
       (r"Control Panel\Mouse", "MouseThreshold2", "0", SZ)]),
  dict(id="rawmouse", page="tweaks", name="Input Queue & Hook Delay Trim", risk="med",
     desc="Lowers low-level input hook delay and trims pointer hover/queue lag (Custom style).",
     reg=[(r"Control Panel\Desktop", "LowLevelHooksTimeout", "1000", SZ),
       (r"Control Panel\Mouse", "MouseHoverTime", "100", SZ),
       (r"Control Panel\Mouse", "MouseHoverWidth", "2", SZ),
       (r"Control Panel\Mouse", "MouseHoverHeight", "2", SZ)]),
  dict(id="mouse_data_q", page="tweaks", name="Mouse Data Queue & Wheel Tune", risk="med", admin=True,
     desc="Increases mouse input buffer size (MouseDataQueueSize=32) to prevent dropped fast flicks.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Services\mouclass\Parameters", "MouseDataQueueSize", 32, DWORD),
       (r"Control Panel\Desktop", "WheelScrollLines", "3", SZ)]),
  dict(id="kbd_data_q", page="tweaks", name="Keyboard Data Queue Boost", risk="med", admin=True,
     desc="Increases keyboard input buffer size (KeyboardDataQueueSize=32) for fast keystrokes.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Services\kbdclass\Parameters", "KeyboardDataQueueSize", 32, DWORD)]),
  dict(id="keyb_resp", page="tweaks", name="Fast Keyboard Repeat & Delay", risk="low",
     desc="Speeds up keyboard key-repeat response and lowers repeat delay for snappy movement/building.",
     reg=[(r"Control Panel\Keyboard", "KeyboardDelay", "0", SZ),
       (r"Control Panel\Keyboard", "KeyboardSpeed", "31", SZ)]),
  dict(id="fsopt", page="tweaks", name="Disable Fullscreen Optimizations",
     desc="Bypasses DWM fullscreen optimization overhead to lower input delay and micro-stutter.",
     reg=[(r"System\GameConfigStore", "GameDVR_FSEBehaviorMode", 2, DWORD),
       (r"System\GameConfigStore", "GameDVR_HonorUserFSEBehaviorMode", 1, DWORD),
       (r"System\GameConfigStore", "GameDVR_DXGIHonorFSEWindowsCompatible", 1, DWORD),
       (r"System\GameConfigStore", "GameDVR_EFSEFeatureFlags", 0, DWORD)]),
  dict(id="gamebar", page="tweaks", name="Disable Xbox Game Bar",
     desc="Disables Game Bar startup panel and controller shortcut.",
     reg=[(r"Software\Microsoft\GameBar", "ShowStartupPanel", 0, DWORD),
       (r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled", 0, DWORD)]),
  dict(id="bgapps", page="tweaks", name="Disable Background Apps",
     desc="Prevents background UWP/search apps from eating RAM and CPU cycles during gameplay.",
     reg=[(r"Software\Microsoft\BackgroundAccessApplications", "GlobalUserDisabled", 1, DWORD),
       (r"Software\Microsoft\Search", "BackgroundAppGlobalToggle", 0, DWORD)]),
  dict(id="anim", page="tweaks", name="Disable Window & Taskbar Animations",
     desc="Disables minimize/maximize and taskbar animations for instant UI response.",
     reg=[(r"Control Panel\Desktop\WindowMetrics", "MinAnimate", "0", SZ),
       (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarAnimations", 0, DWORD)]),
  dict(id="transp", page="tweaks", name="Disable Transparency Effects",
     desc="Turns off acrylic/transparency blur to free up GPU/DWM cycles.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", 0, DWORD)]),
  dict(id="custom_net_tcp", page="tweaks", name="Custom TCP NoDelay & Low Ping", risk="med", admin=True,
     desc="Disables Nagle throttling (TCPNoDelay), sets TTL=64 and Path MTU Discovery for lower ping/delay.",
     reg=[(r"HKLM\SOFTWARE\Microsoft\MSMQ\Parameters", "TCPNoDelay", 1, DWORD),
       (r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters", "DefaultTTL", 64, DWORD),
       (r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters", "EnablePMTUDiscovery", 1, DWORD)]),
  dict(id="net_throt_off", page="tweaks", name="Network & Interrupt Latency Tune", risk="med", admin=True,
     desc="Disables TCP auto-tuning heuristics issues & tunes network adapter interrupt moderation.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters", "TcpTimedWaitDelay", 30, DWORD),
       (r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters", "MaxUserPort", 65534, DWORD)]),

  # ==================== SYSTEM & APP LAG FIXES ====================
  dict(id="menudelay", page="fixes", name="Instant Menu Response",
     desc="Sets MenuShowDelay to 0 so right-click and cascading menus open immediately.",
     reg=[(r"Control Panel\Desktop", "MenuShowDelay", "0", SZ)]),
  dict(id="startdelay", page="fixes", name="Remove Startup Delay",
     desc="Removes Windows artificial startup launch delay so apps load faster.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize", "StartupDelayInMSec", 0, DWORD)]),
  dict(id="apphangfix", page="fixes", name="App Freeze & Hang Recovery", risk="low",
     desc="Shortens HungAppTimeout/WaitToKillAppTimeout and enables AutoEndTasks so frozen apps don't lock Windows.",
     reg=[(r"Control Panel\Desktop", "HungAppTimeout", "1000", SZ),
       (r"Control Panel\Desktop", "WaitToKillAppTimeout", "2000", SZ),
       (r"Control Panel\Desktop", "AutoEndTasks", "1", SZ)]),
  dict(id="shelllagfix", page="fixes", name="Explorer & Shell Lag Fix", risk="low",
     desc="Stops slow network crawling, trims hover delays, and keeps Explorer responsive.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoNetCrawling", 1, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "DisableThumbnailCache", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ExtendedUIHoverTime", 1, DWORD)]),
  dict(id="sticky", page="fixes", name="Disable Sticky / Filter / Toggle Keys",
     desc="Disables StickyKeys, FilterKeys, and ToggleKeys popups and lag triggers in games.",
     reg=[(r"Control Panel\Accessibility\StickyKeys", "Flags", "506", SZ),
       (r"Control Panel\Accessibility\Keyboard Response", "Flags", "122", SZ),
       (r"Control Panel\Accessibility\ToggleKeys", "Flags", "58", SZ)]),
  dict(id="killapp", page="fixes", name="Faster App & Service Close",
     desc="Speeds up closing stalled apps and hung shutdown dialogs.",
     reg=[(r"Control Panel\Desktop", "WaitToKillAppTimeout", "2000", SZ),
       (r"Control Panel\Desktop", "HungAppTimeout", "1000", SZ),
       (r"Control Panel\Desktop", "AutoEndTasks", "1", SZ)]),
  dict(id="ads", page="fixes", name="Disable Suggestions, Tips & Lock Ads",
     desc="Turns off Start menu suggestions, tips, and lock screen ads.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SystemPaneSuggestionsEnabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338388Enabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338389Enabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SoftLandingEnabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "RotatingLockScreenOverlayEnabled", 0, DWORD)]),
  dict(id="ntfs_lagfix", page="fixes", name="NTFS Last Access & 8dot3 Lag Fix", risk="med", admin=True,
     desc="Disables NTFS last-access timestamp writes (NtfsDisableLastAccessUpdate=1) & 8.3 short names for faster file I/O.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\FileSystem", "NtfsDisableLastAccessUpdate", 1, DWORD),
       (r"HKLM\SYSTEM\CurrentControlSet\Control\FileSystem", "NtfsDisable8dot3NameCreation", 1, DWORD)]),
  dict(id="dwm_stutter_fix", page="fixes", name="DWM & Overlay Lag Reduction", risk="low",
     desc="Reduces desktop window/cursor lag and prevents unnecessary visual effects slowdown.",
     reg=[(r"Software\Microsoft\Windows\Dwm", "EnableAeroPeek", 0, DWORD),
       (r"Control Panel\Desktop", "DragFullWindows", "1", SZ)]),

  # ==================== PERFORMANCE TWEAKS ( + + FULL) ====================
  dict(id="vfx", page="perf", name="Best Performance Visual Effects",
     desc="Sets Windows visual effects to Best Performance.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 2, DWORD)]),
  dict(id="hags", page="perf", name="Hardware GPU Scheduling (HAGS)", risk="med", admin=True,
     desc="Enables Hardware-Accelerated GPU Scheduling on supported GPUs. Restart required.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2, DWORD)]),
  dict(id="mmcss", page="perf", name="Multimedia Network Throttling Off", risk="med", admin=True,
     desc="Sets NetworkThrottlingIndex to 0xFFFFFFFF and SystemResponsiveness to 0 (Custom staple).",
     reg=[(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "NetworkThrottlingIndex", 0xFFFFFFFF, DWORD),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "SystemResponsiveness", 0, DWORD)]),
  dict(id="gamepri", page="perf", name="Game GPU & CPU Priority (MMCSS)", risk="low", admin=True,
     desc="Sets high GPU Priority (8), Priority (6), High scheduling & High SFIO priority for Games.",
     reg=[(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "GPU Priority", 8, DWORD),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Priority", 6, DWORD),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Scheduling Category", "High", SZ),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "SFIO Priority", "High", SZ)]),
  dict(id="fgboost", page="perf", name="Foreground Priority Boost (Win32)", risk="low", admin=True,
     desc="Sets Win32PrioritySeparation to 38 (26 hex) for strong foreground/game CPU scheduling.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", 38, DWORD)]),
  dict(id="timer", page="perf", name="Timer Resolution 1ms", risk="high", admin=True, timer=True,
     desc="Requests 1ms system timer resolution for tighter frame pacing while Stormy Tweaks is open.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests", 1, DWORD)]),
  dict(id="fth", page="perf", name="Disable Fault Tolerant Heap", risk="low", admin=True,
     desc="Disables Fault Tolerant Heap overhead.",
     reg=[(r"HKLM\SOFTWARE\Microsoft\FTH", "Enabled", 0, DWORD)]),
  dict(id="latcap", page="perf", name="Latency Cap & Games Task Tuning", risk="med", admin=True,
     desc="Sets Games task Clock Rate=10000, Background Only=False, Affinity=0.",
     reg=[(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Clock Rate", 10000, DWORD),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Background Only", "False", SZ),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Affinity", 0, DWORD)]),
  dict(id="gpupref", page="perf", name="Force Dedicated GPU for Games", risk="high", dyn=gpu_pref,
     desc="Pins games in your library to High Performance GPU in DirectX UserGpuPreferences."),
  dict(id="mmcsslat", page="perf", name="MMCSS Latency Sensitive Mode", risk="med", admin=True,
     desc="Sets NoLazyMode=1, AlwaysOn=1, and Games Latency Sensitive=True.",
     reg=[(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "NoLazyMode", 1, DWORD),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "AlwaysOn", 1, DWORD),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Latency Sensitive", "True", SZ)]),
  dict(id="faststop", page="perf", name="Fast Service Kill Timeout", risk="med", admin=True,
     desc="Lowers WaitToKillServiceTimeout to 2000ms for faster shutdowns/restarts.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control", "WaitToKillServiceTimeout", "2000", SZ)]),
  dict(id="explorer", page="perf", name="Explorer Responsiveness", risk="med",
     desc="Speeds up hover previews, removes icon shadows, and disables network crawling.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ExtendedUIHoverTime", 1, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ListviewShadow", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoNetCrawling", 1, DWORD)]),
  dict(id="audiowm", page="perf", name="Audio & Window Manager Priority", risk="med", admin=True,
     desc="Boosts Audio and Window Manager MMCSS scheduling to prevent audio crackles and UI hitching.",
     reg=[(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Audio", "Scheduling Category", "High", SZ),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Audio", "Priority", 6, DWORD),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Audio", "SFIO Priority", "High", SZ),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Window Manager", "Scheduling Category", "High", SZ),
       (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Window Manager", "Priority", 5, DWORD)]),
  dict(id="gpu_power_lat", page="perf", name="GPU Power Latency Trim", risk="high", admin=True,
     desc="Sets MonitorRefreshLatencyTolerance=1 and TransitionLatency=1 to reduce GPU power-state ramp delay.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers\Power", "MonitorRefreshLatencyTolerance", 1, DWORD),
       (r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers\Power", "TransitionLatency", 1, DWORD)]),
  dict(id="usb_pwr_off", page="perf", name="USB Selective Suspend Off", risk="med", admin=True,
     desc="Disables USB selective suspend / power-down idle delay on USB hubs & controllers.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Services\USB", "DisableSelectiveSuspend", 1, DWORD)]),
  dict(id="nv_preempt_off", page="perf", name="GPU Preemption & TDR Latency Tune", risk="high", admin=True,
     desc="Disables GPU preemption latency overhead (EnablePreemption=0) for smoother frame delivery.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "EnablePreemption", 0, DWORD)]),
  dict(id="mitig", page="perf", name="Disable CPU Mitigations", risk="crit", warn=True, admin=True,
     desc="Disables Spectre/Meltdown mitigations for raw speed. Lowers security. Restart required.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "FeatureSettingsOverride", 3, DWORD),
       (r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "FeatureSettingsOverrideMask", 3, DWORD)]),
  dict(id="vbs", page="perf", name="Disable VBS / Memory Integrity", risk="high", warn=True, admin=True,
     desc="Turns off Virtualization-Based Security & HVCI for FPS/CPU gain. Restart required.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard", "EnableVirtualizationBasedSecurity", 0, DWORD),
       (r"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity", "Enabled", 0, DWORD)]),
  dict(id="kernel", page="perf", name="Kernel Memory Lock & Cache", risk="high", warn=True, admin=True,
     desc="Locks kernel/drivers in RAM (DisablePagingExecutive=1) & LargeSystemCache=1. Best with 16GB+ RAM.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "DisablePagingExecutive", 1, DWORD),
       (r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "LargeSystemCache", 1, DWORD)]),
  dict(id="pwrthrottle", page="perf", name="Disable Power Throttling & QoS", risk="high", admin=True,
     desc="Disables PowerThrottling and QoS packet bandwidth cap.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", 1, DWORD),
       (r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Psched", "NonBestEffortLimit", 0, DWORD)]),
  dict(id="onedrive", page="perf", name="Disable OneDrive Sync", risk="med", admin=True,
     desc="Blocks OneDrive sync/background overhead via policy.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\OneDrive", "DisableFileSyncNGSC", 1, DWORD)]),
  dict(id="svcsplit", page="perf", name="SvcHost RAM Split Threshold", risk="high", admin=True,
     desc="Sets SvcHostSplitThresholdInKB to total installed RAM in KB. Restart required.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control", "SvcHostSplitThresholdInKB", lambda: int(ram()[1] * 1024 * 1024), DWORD)]),
  dict(id="insider", page="perf", name="Disable Windows Insider", risk="low", admin=True,
     desc="Disables preview build checks.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\PreviewBuilds", "AllowBuildPreview", 0, DWORD)]),
  dict(id="wsearch", page="perf", name="Disable Windows Search Index", risk="high", admin=True,
     desc="Stops WSearch background disk indexing. Restart required.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Services\WSearch", "Start", 4, DWORD)]),
  dict(id="mpo", page="perf", name="Disable MPO (Display Flicker/Stutter)", risk="high", admin=True,
     desc="Disables Multi-Plane Overlay (OverlayTestMode=5) to fix flicker/stutter on some GPUs. Restart required.",
     reg=[(r"HKLM\SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", 5, DWORD)]),
  dict(id="errrep", page="perf", name="Disable Windows Error Reporting", risk="low",
     desc="Stops error reporting popups and crash uploads.",
     reg=[(r"Software\Microsoft\Windows\Windows Error Reporting", "Disabled", 1, DWORD),
       (r"Software\Microsoft\Windows\Windows Error Reporting", "DontShowUI", 1, DWORD)]),
  dict(id="sysmain", page="perf", name="Disable SysMain (Superfetch)", risk="med", admin=True,
     desc="Disables SysMain background preloading service. Restart required.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Services\SysMain", "Start", 4, DWORD)]),
  dict(id="prefetch", page="perf", name="Disable Prefetcher", risk="low", admin=True,
     desc="Sets EnablePrefetcher=0 for SSD setups. Restart required.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters", "EnablePrefetcher", 0, DWORD)]),
  dict(id="faststart", page="perf", name="Disable Fast Startup (Hiberboot)", risk="med", admin=True,
     desc="Disables hybrid boot so every startup loads fresh drivers. Restart required.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled", 0, DWORD)]),
  dict(id="power", page="perf", name="High Performance Power Plan",
     desc="Switches active Windows power plan to High Performance.", power=True),

  # ==================== WINDOWS PRIVACY / CEIP / TELEMETRY / BLOAT ====================
  dict(id="ceip_off", page="windows", name="Disable CEIP (Custom)", risk="low", admin=True,
     desc="Sets SQMClient CEIPEnable=0 to turn off Customer Experience Improvement logging.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\SQMClient\Windows", "CEIPEnable", 0, DWORD)]),
  dict(id="telemetry", page="windows", name="Optimize Privacy & Tracking", risk="med",
     desc="Disables advertising ID, tailored experiences, feedback prompts & program tracking.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Privacy", "TailoredExperiencesWithDiagnosticDataEnabled", 0, DWORD),
       (r"Software\Microsoft\Siuf\Rules", "NumberOfSIUFInPeriod", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Start_TrackProgs", 0, DWORD)]),
  dict(id="cortana", page="windows", name="Disable Cortana & Silent Installs", risk="med",
     desc="Turns off Cortana, silent app installs, and preinstalled/OEM suggestions.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\Search", "CortanaConsent", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SilentInstalledAppsEnabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "PreInstalledAppsEnabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "OemPreInstalledAppsEnabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-338387Enabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-310093Enabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SubscribedContent-353698Enabled", 0, DWORD)]),
  dict(id="websearch", page="windows", name="Disable Bing Web Search in Start", risk="med",
     desc="Keeps Windows search local and fast without Bing web suggestions.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\SearchSettings", "IsDynamicSearchBoxEnabled", 0, DWORD),
       (r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", 1, DWORD)]),
  dict(id="copilot", page="windows", name="Disable Copilot & Recall", risk="med",
     desc="Turns off Copilot and Recall AI data analysis where available.",
     reg=[(r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 1, DWORD),
       (r"Software\Policies\Microsoft\Windows\WindowsAI", "DisableAIDataAnalysis", 1, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowCopilotButton", 0, DWORD)]),
  dict(id="taskbar", page="windows", name="Taskbar Cleanup", risk="low",
     desc="Hides Task View, Widgets, Chat, and search box clutter on the taskbar.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowTaskViewButton", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarDa", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarMn", 0, DWORD),
       (r"Software\Microsoft\Windows\CurrentVersion\Search", "SearchboxTaskbarMode", 0, DWORD)]),
  dict(id="shake", page="windows", name="Disable Aero Shake", risk="low",
     desc="Stops windows from minimizing when shaking a title bar.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "DisallowShaking", 1, DWORD)]),
  dict(id="clipboard", page="windows", name="Disable Clipboard History & Sync", risk="low",
     desc="Turns off clipboard history and cloud sync.",
     reg=[(r"Software\Microsoft\Clipboard", "EnableClipboardHistory", 0, DWORD),
       (r"Software\Microsoft\Clipboard", "CloudClipboardAutomaticUpload", 0, DWORD)]),
  dict(id="delivopt", page="windows", name="Disable Delivery Optimization P2P", risk="low", admin=True,
     desc="Stops Windows Update P2P sharing to save bandwidth.",
     reg=[(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config", "DODownloadMode", 0, DWORD)]),
  dict(id="activity", page="windows", name="Disable Activity History", risk="low", admin=True,
     desc="Stops recording and uploading activity feed/timeline.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System", "EnableActivityFeed", 0, DWORD),
       (r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System", "PublishUserActivities", 0, DWORD),
       (r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System", "UploadUserActivities", 0, DWORD)]),
  dict(id="telemlvl", page="windows", name="Minimum Telemetry Level", risk="med", admin=True,
     desc="Sets AllowTelemetry policy to 0 (minimum allowed by edition).",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", 0, DWORD)]),
  dict(id="diagtrack_off", page="windows", name="Disable Connected User Experiences", risk="high", admin=True,
     desc="Disables DiagTrack telemetry service (Start=4). Restart required.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Services\DiagTrack", "Start", 4, DWORD)]),

  # ==================== WIFI TWEAKS ====================
  dict(id="wifipower", page="wifi", name="Max Wireless Performance", risk="med",
     desc="Sets wireless power saving mode to Maximum Performance on AC & battery.",
     wifi=dict(power=True)),
  dict(id="wifiuapsd", page="wifi", name="Disable U-APSD Power Save", risk="med", admin=True,
     desc="Disables U-APSD power save on WiFi adapters to cut latency spikes.",
     wifi=dict(name=r"U-?APSD", vals=[r"^Disabled$", r"Disable", r"^Off$"])),
  dict(id="wifimimo", page="wifi", name="Disable MIMO Power Save", risk="med", admin=True,
     desc="Disables MIMO SMPS power saving on WiFi radio.",
     wifi=dict(name=r"MIMO", vals=[r"No SMPS", r"^Disabled$", r"Disable", r"^Off$"])),
  dict(id="wifi5g", page="wifi", name="Prefer 5GHz Band", risk="med", warn=True, admin=True,
     desc="Prefers 5GHz band for lower interference and higher speeds.",
     wifi=dict(name=r"Prefer(red)? Band|Band Preference", vals=[r"Prefer.*5", r"5.*GHz"])),
  dict(id="wifiroam", page="wifi", name="Max Roaming Aggressiveness", risk="low", admin=True,
     desc="Sets roaming aggressiveness to highest/maximum.",
     wifi=dict(name=r"Roaming Aggressiveness", vals=[r"Highest", r"Maximum"])),
  dict(id="wifitx", page="wifi", name="Max Transmit Power", risk="low", admin=True,
     desc="Sets WiFi transmit power to maximum.",
     wifi=dict(name=r"Transmit Power|Tx Power", vals=[r"Highest", r"Maximum", r"100"])),

  # ==================== EXTRA: GPU / INPUT / DISPLAY (Risxn / EXM tarzi, hepsi geri alinabilir) ====================
  dict(id="cleartype", page="tweaks", name="Smooth Text (ClearType)", risk="low",
     desc="Forces ClearType font smoothing so Windows text stays crisp and smooth.",
     reg=[(r"Control Panel\Desktop", "FontSmoothing", "2", SZ),
       (r"Control Panel\Desktop", "FontSmoothingType", 2, DWORD),
       (r"Control Panel\Desktop", "FontSmoothingOrientation", 1, DWORD)]),
  dict(id="touchfx", page="tweaks", name="Disable Touch & Click Visual Effects", risk="low",
     desc="Turns off touch/gesture visualization overlays that cost a little GPU/DWM time.",
     reg=[(r"Control Panel\Cursors", "ContactVisualization", 0, DWORD),
       (r"Control Panel\Cursors", "GestureVisualization", 0, DWORD)]),
  dict(id="mousesens", page="tweaks", name="Mouse Sensitivity 6/11 (1:1)", risk="low",
     desc="Sets the Windows pointer speed to the neutral 6/11 step so there is no hidden scaling.",
     reg=[(r"Control Panel\Mouse", "MouseSensitivity", "10", SZ)]),
  dict(id="wgo", page="tweaks", name="Optimizations for Windowed Games", risk="low",
     desc="Enables DirectX flip-model upgrade for windowed/borderless games for lower latency.",
     reg=[(r"Software\Microsoft\DirectX\UserGpuPreferences", "DirectXUserGlobalSettings", "SwapEffectUpgradeEnable=1;", SZ)]),
  dict(id="dvr_policy", page="tweaks", name="Block Game DVR (System Policy)", risk="low", admin=True,
     desc="Machine-wide policy that stops Game DVR/capture services from ever starting.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", 0, DWORD)]),
  dict(id="toasts", page="tweaks", name="Silence Toast Notifications", risk="low",
     desc="Turns off pop-up notifications so nothing interrupts or steals focus from a game.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\PushNotifications", "ToastEnabled", 0, DWORD)]),
  dict(id="gpu_msi", page="tweaks", name="MSI Mode for GPU & Network Card", risk="high", warn=True, admin=True,
     dyn=msi_mode, dynmsg="No GPU / network PCI device found",
     desc="Enables Message Signaled Interrupts on your GPU and NIC for lower interrupt latency. Restart required."),
  dict(id="nv_pstate", page="tweaks", name="NVIDIA Max Performance P-State", risk="high", admin=True,
     dyn=gpu_nv, dynmsg="No NVIDIA GPU found",
     desc="Keeps the NVIDIA GPU at its top performance state (no clock ramp delay). Higher idle power/heat. Restart required."),

  # ==================== EXTRA: NETWORK / PING ====================
  dict(id="net_ackfreq", page="network", name="TCP ACK Frequency & NoDelay (per adapter)", risk="med", admin=True,
     dyn=iface_tcp, dynmsg="No active network adapter with an IP found",
     desc="Sets TcpAckFrequency=1, TCPNoDelay=1 and TcpDelAckTicks=0 on your active adapters to send ACKs instantly."),
  dict(id="net_netsh", page="network", name="TCP Stack Tune (netsh)", risk="med", admin=True,
     cmds=dict(on=["netsh int tcp set global autotuninglevel=normal", "netsh int tcp set global rss=enabled",
             "netsh int tcp set global ecncapability=disabled", "netsh int tcp set global timestamps=disabled",
             "netsh int tcp set global initialRto=2000", "netsh int tcp set global nonsackrttresiliency=disabled"],
           off=["netsh int tcp set global autotuninglevel=normal", "netsh int tcp set global ecncapability=default",
             "netsh int tcp set global timestamps=default", "netsh int tcp set global initialRto=3000",
             "netsh int tcp set global nonsackrttresiliency=default"]),
     desc="Normal auto-tuning + RSS, ECN/timestamps off and faster initial retransmit for lower, steadier ping."),
  dict(id="net_eth", page="network", name="Ethernet Power & Interrupt Tune", risk="med", admin=True,
     dyn=eth_tune, dynmsg="No physical Ethernet adapter found (WiFi has its own page)",
     desc="Turns off Ethernet power-saving, Green/EEE and interrupt moderation on your wired adapter. Re-plug cable or restart."),
  dict(id="dnscache", page="network", name="DNS Cache Tune", risk="low", admin=True,
     desc="Keeps good DNS answers cached longer and never caches failed lookups, so lookups stay fast and fresh.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters", "MaxCacheTtl", 86400, DWORD),
       (r"HKLM\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters", "MaxNegativeCacheTtl", 0, DWORD)]),
  dict(id="llmnr", page="network", name="Disable LLMNR / Multicast Name Chatter", risk="low", admin=True,
     desc="Stops LLMNR multicast name lookups to cut background network noise.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient", "EnableMulticast", 0, DWORD)]),
  dict(id="ndu", page="network", name="Disable Network Data Usage Monitor", risk="low", admin=True,
     dyn=svc_off("Ndu"), dynmsg="Ndu service not found",
     desc="Disables the NDU driver (known for RAM growth and network overhead). Restart required."),
  dict(id="wu_nodrv", page="network", name="Block Driver Updates via Windows Update", risk="med", admin=True,
     desc="Stops Windows Update from replacing your GPU/network driver behind your back.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate", "ExcludeWUDriversInQualityUpdate", 1, DWORD)]),

  # ==================== EXTRA: SERVICES / BLOAT (Windows page) ====================
  dict(id="svc_xbox", page="windows", name="Disable Xbox Services", risk="med", warn=True, admin=True,
     dyn=svc_off("XblAuthManager", "XblGameSave", "XboxNetApiSvc", "XboxGipSvc"), dynmsg="Xbox services not found",
     desc="Stops Xbox background services. Breaks Xbox app, Game Pass sign-in and Xbox-only games. Restart required."),
  dict(id="svc_diag", page="windows", name="Disable Diagnostics Services", risk="med", admin=True,
     dyn=svc_off("dmwappushservice", "diagnosticshub.standardcollector.service", "WerSvc", "PcaSvc"),
     dynmsg="Diagnostics services not found",
     desc="Turns off WAP push, diagnostics hub, error reporting and compatibility assistant services. Restart required."),
  dict(id="svc_misc", page="windows", name="Disable Unused Services", risk="med", admin=True,
     dyn=svc_off("Fax", "RetailDemo", "MapsBroker", "lfsvc", "WMPNetworkSvc", "PhoneSvc", "SCardSvr",
           "ScDeviceEnum", "wisvc", "icssvc", "WalletService", "SEMgrSvc", "TrkWks"),
     dynmsg="None of these services exist",
     desc="Fax, retail demo, maps, location, media sharing, smart card, hotspot, wallet and similar. Restart required."),
  dict(id="svc_spool", page="windows", name="Disable Print Spooler (no printer)", risk="med", admin=True,
     dyn=svc_off("Spooler"), dynmsg="Spooler service not found",
     desc="Stops the print spooler. Only use it if you never print. Restart required."),
  dict(id="bgapps_pol", page="windows", name="Block Background Apps (Policy)", risk="med", admin=True,
     desc="Machine-wide policy that stops Store apps from running in the background.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsRunInBackground", 2, DWORD)]),
  dict(id="browser_bg", page="windows", name="Stop Browser Background Run", risk="low", admin=True,
     desc="Stops Edge and Chrome from staying resident (startup boost / background mode) after you close them.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled", 0, DWORD),
       (r"HKLM\SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled", 0, DWORD),
       (r"HKLM\SOFTWARE\Policies\Google\Chrome", "BackgroundModeEnabled", 0, DWORD)]),
  dict(id="wu_noreboot", page="windows", name="No Auto-Restart After Updates", risk="low", admin=True,
     desc="Windows will not restart by itself while you are logged in (no surprise reboot mid-game).",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", "NoAutoRebootWithLoggedOnUsers", 1, DWORD)]),
  dict(id="maint", page="windows", name="Disable Automatic Maintenance", risk="med", admin=True,
     desc="Stops scheduled background maintenance from starting disk/CPU work while you play.",
     reg=[(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\Maintenance", "MaintenanceDisabled", 1, DWORD)]),
  dict(id="storsense", page="windows", name="Disable Storage Sense", risk="low",
     desc="Stops Storage Sense from running automatic cleanups in the background.",
     reg=[(r"Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy", "01", 0, DWORD)]),
  dict(id="widgets", page="windows", name="Disable Widgets & News Feed", risk="low", admin=True,
     desc="Turns off the Widgets / News and Interests process.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", 0, DWORD),
       (r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Windows Feeds", "EnableFeeds", 0, DWORD)]),
  dict(id="location", page="windows", name="Disable Location Tracking", risk="low", admin=True,
     desc="Turns off Windows location services via policy.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors", "DisableLocation", 1, DWORD)]),
  dict(id="syncoff", page="windows", name="Disable Settings Sync", risk="low", admin=True,
     desc="Stops syncing Windows settings to your Microsoft account.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\SettingSync", "DisableSettingSync", 2, DWORD),
       (r"HKLM\SOFTWARE\Policies\Microsoft\Windows\SettingSync", "DisableSettingSyncUserOverride", 1, DWORD)]),
  dict(id="inking", page="windows", name="Disable Inking & Typing Data Collection", risk="low",
     desc="Stops Windows from collecting handwriting and typing data.",
     reg=[(r"Software\Microsoft\InputPersonalization", "RestrictImplicitInkCollection", 1, DWORD),
       (r"Software\Microsoft\InputPersonalization", "RestrictImplicitTextCollection", 1, DWORD)]),
  dict(id="store_auto", page="windows", name="Disable Store Auto-Download", risk="low", admin=True,
     desc="Stops Microsoft Store from downloading app updates in the background.",
     reg=[(r"HKLM\SOFTWARE\Policies\Microsoft\WindowsStore", "AutoDownload", 2, DWORD)]),
  dict(id="remote_assist", page="windows", name="Disable Remote Assistance", risk="low", admin=True,
     desc="Turns off Remote Assistance connections.",
     reg=[(r"HKLM\SYSTEM\CurrentControlSet\Control\Remote Assistance", "fAllowToGetHelp", 0, DWORD)]),

  # ==================== EXTRA: PERFORMANCE ====================
  dict(id="ultperf", page="perf", name="Ultimate Performance Power Plan", risk="med", admin=True, power=True,
     scheme=ULT_PERF,
     desc="Activates the hidden Ultimate Performance plan: no core parking, no CPU clock ramp delay. Desktops only."),
  dict(id="bcd_timer", page="perf", name="Timer Tune (Dynamic Tick Off)", risk="high", warn=True, admin=True,
     cmds=dict(on=["bcdedit /set disabledynamictick yes", "bcdedit /set tscsyncpolicy enhanced"],
           off=["bcdedit /deletevalue disabledynamictick", "bcdedit /deletevalue tscsyncpolicy"]),
     desc="Boot-config timer tweaks for steadier frame pacing. Results vary by CPU; reverting restores defaults. Restart required."),
  dict(id="memcomp", page="perf", name="Memory Compression & Page Combining Off", risk="high", admin=True,
     cmds=dict(on=['powershell -NoProfile -Command "Disable-MMAgent -MemoryCompression; Disable-MMAgent -PageCombining"'],
           off=['powershell -NoProfile -Command "Enable-MMAgent -MemoryCompression; Enable-MMAgent -PageCombining"']),
     desc="Turns off RAM compression and page combining to save CPU. Only for 16GB+ RAM. Restart required."),
  dict(id="hiber", page="perf", name="Disable Hibernation", risk="med", admin=True,
     cmds=dict(on=["powercfg /hibernate off"], off=["powercfg /hibernate on"]),
     desc="Removes hiberfil.sys (several GB) and turns off hibernate/fast startup file writes."),
]

PING_HOST = "1.1.1.1"
SECTION = {"tweaks": "Full FPS / Low-Delay Tweaks",
      "windows": "Windows Privacy, Services & Debloat",
      "network": "Network, TCP & Ping Tweaks",
      "fixes": "System, File I/O & App Lag Fixes",
      "perf": "Performance, GPU & Scheduler Tweaks",
      "wifi": "WiFi Adapter Tweaks"}
SECTION_SUB = {"wifi": "WiFi adapters only, Ethernet untouched",
        "network": "TCP/IP stack and wired adapter · WiFi has its own page",
        "fixes": "Fixes app freezes, laggy menus, disk I/O & UI delays"}
WIFI_SUB = "19cbb8fa-5279-450e-9fac-8a3d5fedd0c1"
WIFI_SET = "12bbebe6-58d6-4636-95bb-3217ef867c1a"
RISK = {"crit": ("#ff6b6b", "#3a1216"), "low": ("#34d399", "#10261f"), "med": ("#fbbf24", "#2a2210"), "high": ("#f87171", "#2a1216")}
REC = {"gamemode", "dvr", "mouse", "rawmouse", "mouse_data_q", "kbd_data_q", "keyb_resp",
    "menudelay", "startdelay", "apphangfix", "shelllagfix", "ntfs_lagfix", "dwm_stutter_fix",
    "fsopt", "gamebar", "bgapps", "anim", "sticky", "killapp", "ads", "telemetry", "ceip_off",
    "cortana", "websearch", "copilot", "mmcss", "gamepri", "fgboost", "fth", "errrep",
    "insider", "delivopt", "activity", "explorer", "usb_pwr_off", "custom_net_tcp",
    "cleartype", "touchfx", "wgo", "dvr_policy", "llmnr", "browser_bg", "wu_noreboot", "storsense",
    "widgets", "inking", "syncoff", "remote_assist"}
ICON_FONT = "Segoe MDL2 Assets"
NAV = [("dashboard", "Dashboard", "Rig overview · one-click", "\ue80f"),
    ("monitor", "Monitor", "Live CPU · RAM · GPU", "\ue9d2"),
    ("booster", "Games & Lag", "Game launch · unfreeze apps", "\ue7fc"),
    ("tweaks", "Tweaks", "Custom FPS & delay", "\ue713"),
    ("network", "Network", "Ping · TCP · adapter", "\ue774"),
    ("windows", "Windows", "Privacy · CEIP · debloat", "\ue72e"),
    ("wifi", "WiFi", "Wireless adapter · latency", "\ue701"),
    ("fixes", "Fixes", "App lag · hang & UI fixes", "\ue90f"),
    ("perf", "Performance Mode", "Power plan · GPU · MMCSS", "\ue945")]


def run(cmd, timeout=15):
  try:
    return subprocess.run(cmd, capture_output=True, text=True, shell=True,
               timeout=timeout, creationflags=0x08000000)
  except Exception:
    return subprocess.CompletedProcess(cmd, 1, "", "")


def load():
  d = {"reg": {}, "power": None, "applied": [], "games": []}
  if os.path.exists(DATA):
    try:
      with open(DATA, encoding="utf-8") as f:
        d.update(json.load(f))
    except Exception:
      pass
  return d


def save(d):
  with open(DATA, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2)


def hk(path):
  if path.startswith("HKLM\\"):
    return winreg.HKEY_LOCAL_MACHINE, path[5:]
  return winreg.HKEY_CURRENT_USER, path


def is_admin():
  try:
    return bool(ctypes.windll.shell32.IsUserAnAdmin())
  except Exception:
    return False


def read_reg(path, name):
  root, sub = hk(path)
  try:
    with winreg.OpenKey(root, sub) as k:
      v, t = winreg.QueryValueEx(k, name)
      return [v, t]
  except OSError:
    return None


def write_reg(path, name, value, typ):
  root, sub = hk(path)
  with winreg.CreateKey(root, sub) as k:
    winreg.SetValueEx(k, name, 0, typ, value)


def delete_reg(path, name):
  root, sub = hk(path)
  try:
    with winreg.OpenKey(root, sub, 0, winreg.KEY_SET_VALUE) as k:
      winreg.DeleteValue(k, name)
  except OSError:
    pass


def active_scheme():
  out = run("powercfg /getactivescheme").stdout
  return out.split(":")[1].split()[0] if ":" in out else None


def ps(script, timeout=40):
  try:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-Command", script], capture_output=True, text=True, timeout=timeout,
               creationflags=0x08000000)
  except Exception:
    return subprocess.CompletedProcess(script, 1, "", "")


def psq(s):
  return "'" + str(s).replace("'", "''") + "'"


WIFI_FILTER = ("Get-NetAdapter -Physical | Where-Object { $_.PhysicalMediaType -eq 'Native 802.11' -or "
        "$_.InterfaceDescription -match 'Wi-?Fi|Wireless|802\\.11' }")


def wifi_set(name_pat, val_pats):
  script = (
    "$res=@(); " + WIFI_FILTER + " | ForEach-Object { $a=$_.Name; "
    "$p=Get-NetAdapterAdvancedProperty -Name $a -ErrorAction SilentlyContinue | "
    "Where-Object { $_.DisplayName -match " + psq(name_pat) + " } | Select-Object -First 1; "
    "if($p){ $t=$null; foreach($x in @(" + ",".join(psq(v) for v in val_pats) + ")){ "
    "$t=$p.ValidDisplayValues | Where-Object { $_ -match $x } | Select-Object -First 1; if($t){break} } "
    "if($t){ $old=$p.DisplayValue; try { Set-NetAdapterAdvancedProperty -Name $a -DisplayName $p.DisplayName "
    "-DisplayValue $t -ErrorAction Stop; $res += [pscustomobject]@{a=$a;n=$p.DisplayName;o=$old;v=$t} } catch {} } } }; "
    "ConvertTo-Json -InputObject @($res) -Compress")
  out = ps(script).stdout.strip()
  try:
    data = json.loads(out) if out else []
  except ValueError:
    return []
  return [data] if isinstance(data, dict) else data


def wifi_restore(items):
  for it in items:
    ps(f"Set-NetAdapterAdvancedProperty -Name {psq(it['a'])} -DisplayName {psq(it['n'])} "
      f"-DisplayValue {psq(it['o'])} -ErrorAction SilentlyContinue")


def wifi_power_get():
  out = run(f"powercfg /query SCHEME_CURRENT {WIFI_SUB} {WIFI_SET}").stdout
  vals = [int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]+)", out)]
  return (vals[-2], vals[-1]) if len(vals) >= 2 else None


def wifi_apply(t, d):
  spec = t["wifi"]
  store = d.setdefault("wifi", {})
  if spec.get("power"):
    cur = wifi_power_get()
    if cur is None:
      raise ValueError("no wireless power setting found on this PC")
    store[t["id"]] = {"scheme": active_scheme(), "ac": cur[0], "dc": cur[1]}
    run(f"powercfg /setacvalueindex SCHEME_CURRENT {WIFI_SUB} {WIFI_SET} 0")
    run(f"powercfg /setdcvalueindex SCHEME_CURRENT {WIFI_SUB} {WIFI_SET} 0")
    run("powercfg /setactive SCHEME_CURRENT")
    return
  changes = wifi_set(spec["name"], spec["vals"])
  if not changes:
    raise ValueError("no WiFi adapter found, or your driver doesn't support this setting")
  store[t["id"]] = changes


def wifi_revert(t, d):
  saved = d.get("wifi", {}).pop(t["id"], None)
  if not saved:
    return
  if t["wifi"].get("power"):
    sch = saved.get("scheme") or "SCHEME_CURRENT"
    run(f"powercfg /setacvalueindex {sch} {WIFI_SUB} {WIFI_SET} {saved['ac']}")
    run(f"powercfg /setdcvalueindex {sch} {WIFI_SUB} {WIFI_SET} {saved['dc']}")
    run("powercfg /setactive SCHEME_CURRENT")
  else:
    wifi_restore(saved)


def apply_tweak(t, d):
  if t.get("admin") and not is_admin():
    raise PermissionError("run as administrator")
  if t.get("wifi"):
    wifi_apply(t, d)
  regs = list(t.get("reg", []))
  if t.get("dyn"):
    extra = t["dyn"](d)
    if not extra:
      raise ValueError(t.get("dynmsg", "add games in the Games page first"))
    d.setdefault("dynkeys", {})[t["id"]] = [[p, n] for p, n, _, _ in extra]
    regs += extra
  for path, name, val, typ in regs:
    key = f"{path}|{name}"
    if key not in d["reg"]:
      d["reg"][key] = read_reg(path, name)
    write_reg(path, name, val() if callable(val) else val, typ)
  if t.get("cmds"):
    bad = sum(1 for c in t["cmds"]["on"] if run(c, 60).returncode != 0)
    if bad and bad == len(t["cmds"]["on"]):
      raise RuntimeError("command failed (run as administrator?)")
  if t.get("timer"):
    ctypes.windll.winmm.timeBeginPeriod(1)
  if t.get("power"):
    scheme = t.get("scheme", HIGH_PERF)
    if d["power"] is None:
      d["power"] = active_scheme()
    if run(f"powercfg /setactive {scheme}").returncode != 0:
      dup = run(f"powercfg /duplicatescheme {scheme}").stdout
      if ":" not in dup:
        raise RuntimeError("this power plan is not available on this PC")
      run(f"powercfg /setactive {dup.split(':')[1].split()[0]}")
  if t["id"] not in d["applied"]:
    d["applied"].append(t["id"])


def revert_tweak(t, d):
  if t.get("wifi"):
    wifi_revert(t, d)
  regs = list(t.get("reg", [])) + [(p, n, None, None) for p, n in d.get("dynkeys", {}).pop(t["id"], [])]
  for path, name, val, typ in regs:
    key = f"{path}|{name}"
    if key in d["reg"]:
      old = d["reg"].pop(key)
      if old is None:
        delete_reg(path, name)
      else:
        write_reg(path, name, old[0], old[1])
  if t.get("cmds"):
    for c in t["cmds"]["off"]:
      run(c, 60)
  if t.get("timer"):
    ctypes.windll.winmm.timeEndPeriod(1)
  if t.get("power") and d["power"]:
    run(f"powercfg /setactive {d['power']}")
    d["power"] = None
  if t["id"] in d["applied"]:
    d["applied"].remove(t["id"])


def auto_backup(tweaks, d, keep=20):
  def esc(x):
    return str(x).replace("\\", "\\\\").replace('"', '\\"')

  keys, wifi = {}, False
  for t in tweaks:
    if t.get("admin") and not is_admin():
      continue
    wifi = wifi or bool(t.get("wifi"))
    regs = list(t.get("reg", []))
    if t.get("dyn"):
      try:
        regs += t["dyn"](d)
      except Exception:
        pass
    for path, name, _, _ in regs:
      root = "HKEY_LOCAL_MACHINE" if path.startswith("HKLM\\") else "HKEY_CURRENT_USER"
      sub = path[5:] if path.startswith("HKLM\\") else path
      old = read_reg(path, name)
      n = f'"{esc(name)}"'
      if old is None:
        line = f"{n}=-"
      elif old[1] == DWORD:
        line = f"{n}=dword:{old[0] & 0xFFFFFFFF:08x}"
      elif old[1] == SZ:
        line = f'{n}="{esc(old[0])}"'
      else:
        continue
      keys.setdefault(f"{root}\\{sub}", {}).setdefault(name, line)
  if not keys and not wifi:
    return None

  base = os.path.join(DIR, "backups")
  folder = os.path.join(base, time.strftime("%Y%m%d_%H%M%S"))
  while os.path.exists(folder):
    folder += "_b"
  os.makedirs(folder)
  if keys:
    with open(os.path.join(folder, "restore.reg"), "w", encoding="utf-16", newline="") as f:
      f.write("Windows Registry Editor Version 5.00\r\n\r\n")
      for key, vals in keys.items():
        f.write(f"[{key}]\r\n" + "\r\n".join(vals.values()) + "\r\n\r\n")
  if wifi:
    out = os.path.join(folder, "wifi-settings.csv")
    ps(WIFI_FILTER + " | ForEach-Object { Get-NetAdapterAdvancedProperty -Name $_.Name } | "
      "Select-Object Name,DisplayName,DisplayValue,RegistryKeyword,RegistryValue | "
      "Export-Csv -NoTypeInformation -Encoding UTF8 " + psq(out))
  try:
    shutil.copyfile(DATA, os.path.join(folder, "app-state.json"))
  except OSError:
    pass
  try:
    old_dirs = sorted(x for x in os.listdir(base) if os.path.isdir(os.path.join(base, x)))
    for x in old_dirs[:-keep]:
      shutil.rmtree(os.path.join(base, x), ignore_errors=True)
  except OSError:
    pass
  return folder


def clean_temp():
  n = 0
  for root, _, files in os.walk(tempfile.gettempdir()):
    for f in files:
      try:
        os.remove(os.path.join(root, f))
        n += 1
      except OSError:
        pass
  return n


def fix_stuck_apps():
  """Closes non-responding user windows safely and flushes DNS/temp cache."""
  script = (
    "$hung = Get-Process | Where-Object { -not $_.Responding -and $_.MainWindowTitle -ne '' }; "
    "$cnt = 0; "
    "foreach ($p in $hung) { "
    " try { Stop-Process -Id $p.Id -Force -ErrorAction Stop; $cnt++ } catch {} "
    "}; "
    "$cnt"
  )
  out = ps(script, timeout=15).stdout.strip()
  run("ipconfig /flushdns")
  try:
    return int(out.splitlines()[-1])
  except Exception:
    return 0


class MEM(ctypes.Structure):
  _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong),
        ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
        ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong),
        ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong),
        ("ae", ctypes.c_ulonglong)]


def ram():
  m = MEM()
  m.l = ctypes.sizeof(m)
  ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
  return m.ap / 2**30, m.tp / 2**30


def refresh_rate():
  try:
    dc = ctypes.windll.user32.GetDC(0)
    hz = ctypes.windll.gdi32.GetDeviceCaps(dc, 116)
    ctypes.windll.user32.ReleaseDC(0, dc)
    return hz
  except Exception:
    return 0


class SPS(ctypes.Structure):
  _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("pct", ctypes.c_ubyte),
        ("sys", ctypes.c_ubyte), ("life", ctypes.c_ulong), ("full", ctypes.c_ulong)]


def is_desktop():
  try:
    st = SPS()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st))
    return st.flag == 128
  except Exception:
    return True


def cpu_name():
  try:
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
              r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
      return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
  except OSError:
    return platform.processor()


def gpu_name():
  out = run('powershell -NoProfile -Command "(Get-CimInstance Win32_VideoController | '
       'Select-Object -First 1).Name"', 10).stdout.strip()
  return out or "Unknown"


class FT(ctypes.Structure):
  _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]


_prev = [None]


def cpu_load():
  a, b, c = FT(), FT(), FT()
  ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(a), ctypes.byref(b), ctypes.byref(c))
  idle, kern, user = [(x.hi << 32) | x.lo for x in (a, b, c)]
  prev, _prev[0] = _prev[0], (idle, kern, user)
  if not prev:
    return 0.0
  tot = (kern - prev[1]) + (user - prev[2])
  return max(0.0, min(100.0, (tot - (idle - prev[0])) * 100.0 / tot)) if tot else 0.0


def ram_pct():
  m = MEM()
  m.l = ctypes.sizeof(m)
  ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
  return m.load


class DEVMODE(ctypes.Structure):
  _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", ctypes.c_ushort),
        ("dmDriverVersion", ctypes.c_ushort), ("dmSize", ctypes.c_ushort),
        ("dmDriverExtra", ctypes.c_ushort), ("dmFields", ctypes.c_ulong),
        ("dmPositionX", ctypes.c_long), ("dmPositionY", ctypes.c_long),
        ("dmDisplayOrientation", ctypes.c_ulong), ("dmDisplayFixedOutput", ctypes.c_ulong),
        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short), ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_ushort), ("dmBitsPerPel", ctypes.c_ulong),
        ("dmPelsWidth", ctypes.c_ulong), ("dmPelsHeight", ctypes.c_ulong),
        ("dmDisplayFlags", ctypes.c_ulong), ("dmDisplayFrequency", ctypes.c_ulong),
        ("dmICMMethod", ctypes.c_ulong), ("dmICMIntent", ctypes.c_ulong),
        ("dmMediaType", ctypes.c_ulong), ("dmDitherType", ctypes.c_ulong),
        ("dmReserved1", ctypes.c_ulong), ("dmReserved2", ctypes.c_ulong),
        ("dmPanningWidth", ctypes.c_ulong), ("dmPanningHeight", ctypes.c_ulong)]


def set_max_hz():
  u = ctypes.windll.user32
  dm = DEVMODE()
  dm.dmSize = ctypes.sizeof(dm)
  if not u.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):
    return None
  w, h, bpp, cur = dm.dmPelsWidth, dm.dmPelsHeight, dm.dmBitsPerPel, dm.dmDisplayFrequency
  best, i = cur, 0
  m = DEVMODE()
  m.dmSize = ctypes.sizeof(m)
  while u.EnumDisplaySettingsW(None, i, ctypes.byref(m)):
    if (m.dmPelsWidth, m.dmPelsHeight, m.dmBitsPerPel) == (w, h, bpp) and m.dmDisplayFrequency > best:
      best = m.dmDisplayFrequency
    i += 1
  if best == cur:
    return cur, cur, w, h
  dm.dmDisplayFrequency = best
  dm.dmFields |= 0x400000
  if u.ChangeDisplaySettingsW(ctypes.byref(dm), 2) != 0:
    return None
  if u.ChangeDisplaySettingsW(ctypes.byref(dm), 1) != 0:
    return None
  return cur, best, w, h


ctk.set_appearance_mode("dark")
STY = {"purple": ("#7c3aed", "#9333ea", "white", "#8b5cf6"),
    "green": ("#10b981", "#34d399", "white", "#10b981"),
    "dark": ("#181129", "#281c45", "#f3e8ff", "#3b2866"),
    "red": ("#1f0c14", "#361220", "#fda4af", "#541930")}


FONT = "Segoe UI"
FONT_SB = "Segoe UI Semibold"


def F(size, weight="normal"):
  if weight == "bold":
    return ctk.CTkFont(family=FONT_SB, size=size, weight="normal")
  return ctk.CTkFont(family=FONT, size=size, weight="normal")


def lerp(a, b, t):
  x = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
  y = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
  return "#%02x%02x%02x" % tuple(int(p + (q - p) * t) for p, q in zip(x, y))


class SBtn(ctk.CTkButton):
  def __init__(self, parent, text, style, cmd, h=40, fs=13, w=140):
    base, hov, fg, border = STY[style]
    super().__init__(parent, text=text, fg_color=base, hover=False, text_color=fg, corner_radius=h // 2,
             width=w, height=h, border_width=1, border_color=border, font=F(fs, "bold"), command=cmd)
    self.base, self.hov, self.t, self.goal, self.busy = base, hov, 0.0, 0.0, False
    self.bind("<Enter>", lambda e: self.go(1.0))
    self.bind("<Leave>", lambda e: self.go(0.0))

  def go(self, goal):
    self.goal = goal
    if not self.busy:
      self.busy = True
      self.step()

  def step(self):
    d = self.goal - self.t
    self.t = self.goal if abs(d) < 0.2 else self.t + (0.2 if d > 0 else -0.2)
    self.configure(fg_color=lerp(self.base, self.hov, self.t))
    if self.t != self.goal:
      self.after(16, self.step)
    else:
      self.busy = False


def btn(parent, text, style, cmd, h=40, fs=13, w=140):
  return SBtn(parent, text, style, cmd, h, fs, w)


class SmoothScroll(ctk.CTkScrollableFrame):
  """Fare tekerlegi ile ataletli/yumusak kaydirma (ctk'nin adim adim kaydirmasi yerine)."""
  _sm_job = None
  _sm_cur = 0.0
  _sm_target = 0.0

  def _mouse_wheel_all(self, event):
    try:
      if getattr(self, "_shift_pressed", False):
        return super()._mouse_wheel_all(event)
      if not self.check_if_master_is_canvas(event.widget):
        return
      cv = self._parent_canvas
      if cv.yview() == (0.0, 1.0):
        return
      bb = cv.bbox("all")
      total = max(1, bb[3] - bb[1])
      room = max(0, total - cv.winfo_height())
      base = self._sm_target if self._sm_job is not None else cv.yview()[0] * total
      self._sm_target = min(max(base - event.delta * 0.9, 0), room)
      if self._sm_job is None:
        self._sm_cur = cv.yview()[0] * total
        self._sm_step()
    except Exception:
      try:
        super()._mouse_wheel_all(event)
      except Exception:
        pass

  def _sm_step(self):
    try:
      cv = self._parent_canvas
      bb = cv.bbox("all")
      total = max(1, bb[3] - bb[1])
      d = self._sm_target - self._sm_cur
      if abs(d) < 0.5:
        self._sm_cur = self._sm_target
        self._sm_job = None
      else:
        self._sm_cur += d * 0.22
        self._sm_job = self.after(10, self._sm_step)
      cv.yview_moveto(self._sm_cur / total)
    except Exception:
      self._sm_job = None


def smooth_runtime():
  """Animasyon ve kaydirma icin: 1ms timer, daha az GC kesintisi, hizli thread gecisi."""
  try:
    ctypes.windll.winmm.timeBeginPeriod(1)
  except Exception:
    pass
  try:
    gc.set_threshold(50000, 20, 20)
    sys.setswitchinterval(0.001)
  except Exception:
    pass


smooth_runtime()


def pill(parent, text, fg, bg):
  return ctk.CTkLabel(parent, text=text, text_color=fg, fg_color=bg, corner_radius=9, height=18,
            width=0, font=ctk.CTkFont(family=FONT_SB, size=10, weight="normal"))


class App(ctk.CTk):
  def __init__(s):
    super().__init__(fg_color=BG)
    try:
      s.attributes("-alpha", 0.0)
    except Exception:
      pass
    s.title(APP)
    f = max(1.0, s.winfo_fpixels('1i') / 96)
    sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
    lw = int(max(900, min(1280, sw / f - 40)))
    lh = int(max(600, min(820, sh / f - 90)))
    s.geometry(f"{lw}x{lh}")
    s.minsize(min(1000, lw), min(640, lh))
    try:
      tk.Tk.geometry(s, "+%d+%d" % (max(0, (sw - lw * f) // 2), max(0, (sh - lh * f) // 2 - 20)))
    except Exception:
      pass
    s.jobs, s.hidden = {}, False
    s.scs, s.order, s.wraps, s.lay = {}, {}, {}, {}
    s.d = load()
    if "timer" in s.d["applied"]:
      try:
        ctypes.windll.winmm.timeBeginPeriod(1)
      except Exception:
        pass
    s.pages, s.navs, s.switches, s.stat = {}, {}, {}, {}
    s.cards, s.applybtn = {}, {}
    s.fades, s.pills, s.navfade = {}, {}, {}
    s.cur, s.sel, s.toast_w = None, None, None
    s.q = queue.Queue()
    s.gpu_txt = ""
    s.toast_job, s.toast_lbl = None, None
    s.hist = {"CPU": [], "RAM": [], "GPU": []}
    s.slow = {"gpu": None, "temp": None, "ping": None}
    s.mtab = "CPU"

    s.tip, s.tip_job = None, None
    s.collapsed = bool(s.d.get("collapsed", lw < 1180))
    side = ctk.CTkFrame(s, width=76 if s.collapsed else 250, corner_radius=0, fg_color=SIDE)
    side.pack(side="left", fill="y")
    side.pack_propagate(False)
    s.sidebar = side
    s.head = ctk.CTkFrame(side, fg_color=SIDE)
    s.head.pack(fill="x", pady=(22, 18))
    logo = ctk.CTkFrame(s.head, width=44, height=44, corner_radius=22, fg_color="#28164a",
              border_width=1, border_color="#6d28d9")
    logo.pack(side="left")
    logo.pack_propagate(False)
    ctk.CTkLabel(logo, text="\uE945", font=ctk.CTkFont(ICON_FONT, size=20),
           text_color="#c084fc").place(relx=.5, rely=.5, anchor="center")
    s.brand = ctk.CTkFrame(s.head, fg_color=SIDE)
    ctk.CTkLabel(s.brand, text="STORMY TWEAKS", font=F(16, "bold"), text_color="white",
           anchor="w").pack(fill="x")
    for key, title, sub, icon in NAV:
      s.nav_item(side, key, title, sub, icon)
    s.tog_item(side)
    s.apply_side()

    main = ctk.CTkFrame(s, fg_color=BG, corner_radius=0)
    main.pack(side="left", fill="both", expand=True)
    ctk.CTkLabel(main, text=f"STORMY TWEAKS {VER}", font=F(11, "bold"),
           text_color="#7c5bb3").pack(anchor="w", padx=30, pady=(14, 0))
    s.body = ctk.CTkFrame(main, fg_color=BG, corner_radius=0)
    s.body.pack(fill="both", expand=True, padx=28, pady=(8, 16))

    s.build_dashboard()
    s.builders = {
      "monitor": s.build_monitor,
      "booster": s.build_booster,
      "tweaks": lambda: s.tweak_page("tweaks", "Tweaks", "Full FPS, input & network low-delay tweaks"),
      "windows": lambda: s.tweak_page("windows", "Windows Settings", "Privacy, CEIP/telemetry and clutter you can switch off"),
      "network": lambda: s.tweak_page("network", "Network", "TCP stack, adapter and DNS tweaks for lower, steadier ping"),
      "wifi": lambda: s.tweak_page("wifi", "WiFi", "Wireless adapter tweaks for lower latency and a stable signal"),
      "fixes": lambda: s.tweak_page("fixes", "Fixes", "App lag, frozen windows, I/O and system delay fixes"),
      "perf": lambda: s.tweak_page("perf", "Performance Mode", "Power plan, GPU & MMCSS scheduler tweaks"),
    }
    s.show("dashboard")
    s.log(f"Stormy Tweaks {VER} ready ({len(TWEAKS)} tweaks loaded).")
    s.bg(gpu_name, s.set_gpu)
    s.pump()
    s.start_monitor()
    s.low_priority()
    s.after(2500, s.trim)
    s.bind("<Unmap>", lambda e: s.on_min(True) if e.widget is s else None)
    s.bind("<Map>", lambda e: s.on_min(False) if e.widget is s else None)
    s.update_idletasks()
    s.protocol("WM_DELETE_WINDOW", s.fast_close)
    s.after(60, s.reveal)
    s.after(2200, s.prebuild)
    s.after(350, s.style_window)

  def reveal(s, i=0):
    a = min(1.0, (i + 1) / 6)
    try:
      s.attributes("-alpha", a)
    except Exception:
      return
    if a < 1.0:
      s.after(14, s.reveal, i + 1)

  def style_window(s):
    try:
      hwnd = ctypes.windll.user32.GetParent(s.winfo_id())
      dwm = ctypes.windll.dwmapi

      def put(attr, val):
        v = ctypes.c_int(val)
        dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), 4)

      def bgr(h):
        return (int(h[5:7], 16) << 16) | (int(h[3:5], 16) << 8) | int(h[1:3], 16)
      put(20, 1)
      put(33, 2)
      put(35, bgr(BG))
      put(34, bgr(BORDER))
      put(36, bgr(TXT))
    except Exception:
      pass

  def prebuild(s):
    """Diger sayfalari arka planda (gizliyken) hazirla: ilk gecis anlik olsun."""
    if s.hidden:
      s.after(1500, s.prebuild)
      return
    for key in ("tweaks", "network", "windows", "fixes", "perf", "wifi", "booster", "monitor"):
      if key not in s.pages and key in s.builders:
        try:
          s.builders[key]()
        except Exception:
          pass
        s.after(900, s.prebuild)
        return

  def fast_close(s):
    """Pencereyi hemen gizle, veriyi kaydet, islemi aninda bitir (widget tek tek yok edilmesin)."""
    try:
      s.withdraw()
    except Exception:
      pass
    try:
      save(s.d)
    except Exception:
      pass
    os._exit(0)

  def on_min(s, v):
    s.hidden = v

  def deb(s, name, ms, fn):
    j = s.jobs.get(name)
    if j is not None:
      try:
        s.after_cancel(j)
      except Exception:
        pass
    s.jobs[name] = s.after(ms, fn)

  def pump(s):
    while True:
      try:
        fn = s.q.get_nowait()
      except queue.Empty:
        break
      try:
        fn()
      except Exception:
        pass
    s.after(1000 if s.hidden else 120, s.pump)

  def bg(s, work, done=None):
    def run_it():
      try:
        res = work()
      except Exception:
        res = None
      if done:
        s.q.put(lambda: done(res))
    threading.Thread(target=run_it, daemon=True).start()

  def set_gpu(s, name):
    s.gpu_txt = name or "Unknown"
    s.hw["gpu"].configure(text=s.gpu_txt)
    if "monitor" in s.pages:
      s.mon_gpu.configure(text=s.gpu_txt)

  def low_priority(s):
    try:
      k = ctypes.windll.kernel32
      k.GetCurrentProcess.restype = ctypes.c_void_p
      k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
      k.SetPriorityClass(k.GetCurrentProcess(), 0x20)
    except Exception:
      pass

  def trim(s):
    # Bilerek bos: working-set bosaltmak + gc.collect() kucult/ac ve sayfa gecislerinde takilma yaratiyordu.
    return

  def backup_for(s, tweaks):
    try:
      if auto_backup(tweaks, s.d):
        s.log("Backup saved automatically")
    except Exception as e:
      s.log(f"Backup failed: {e}")

  def flush_dns(s):
    s.bg(lambda: run("ipconfig /flushdns"), lambda r: s.log("DNS cache flushed"))

  def clean(s):
    s.bg(clean_temp, lambda n: s.log(f"Temp cleaned: {n} files"))

  def fix_app_lags_now(s):
    s.bg(fix_stuck_apps, lambda n: s.log(f"Cleared {n} hung app(s) & flushed DNS/lag caches"))

  def nav_item(s, parent, key, title, sub, icon):
    fr = ctk.CTkFrame(parent, width=226, height=50, corner_radius=25, fg_color=SIDE,
             border_width=1, border_color=SIDE)
    fr.pack(pady=2, padx=12, fill="x")
    fr.pack_propagate(False)
    ic = ctk.CTkLabel(fr, text=icon, font=ctk.CTkFont(ICON_FONT, size=20), text_color=MUTED)
    t = ctk.CTkLabel(fr, text=title, font=F(13, "bold"), text_color=TXT, anchor="w")
    u = ctk.CTkLabel(fr, text=sub, font=F(10), text_color=MUTED, anchor="w")
    for w in (fr, ic, t, u):
      w.bind("<Button-1>", lambda e, k=key: s.show(k))
      w.bind("<Enter>", lambda e, k=key, f=fr, a=title, b=sub: s.nav_hover(k, True, f, a, b))
      w.bind("<Leave>", lambda e, k=key: s.nav_hover(k, False))
    s.navs[key] = (fr, ic, t, u)

  def tog_item(s, parent):
    fr = ctk.CTkFrame(parent, width=226, height=44, corner_radius=22, fg_color=SIDE,
             border_width=1, border_color=SIDE)
    fr.pack(side="bottom", pady=(0, 16), padx=12, fill="x")
    fr.pack_propagate(False)
    ic = ctk.CTkLabel(fr, text="\ue700", font=ctk.CTkFont(ICON_FONT, size=18), text_color=MUTED)
    t = ctk.CTkLabel(fr, text="Collapse menu", font=F(12), text_color=MUTED, anchor="w")
    for w in (fr, ic, t):
      w.bind("<Button-1>", lambda e: s.toggle_side())
      w.bind("<Enter>", lambda e, f=fr, a=ic: (f.configure(fg_color="#140e24"), a.configure(text_color="#d8b4fe")))
      w.bind("<Leave>", lambda e, f=fr, a=ic: (f.configure(fg_color=SIDE), a.configure(text_color=MUTED)))
    s.tog = (fr, ic, t)

  def toggle_side(s):
    s.collapsed = not s.collapsed
    s.d["collapsed"] = s.collapsed
    save(s.d)
    s.apply_side()

  def apply_side(s):
    c = s.collapsed
    s.sidebar.configure(width=76 if c else 250)
    s.head.pack_configure(padx=16 if c else 18)
    if c:
      s.brand.pack_forget()
    else:
      s.brand.pack(side="left", padx=(12, 0))
    for fr, ic, t, u in s.navs.values():
      fr.configure(width=50 if c else 226, height=50 if c else 56, corner_radius=25 if c else 28)
      fr.pack_configure(fill="none" if c else "x", padx=0 if c else 12)
      if c:
        t.place_forget()
        u.place_forget()
        ic.place(relx=.5, x=0, rely=.5, anchor="center")
      else:
        ic.place(relx=0, x=26, rely=.5, anchor="center")
        t.place(x=52, y=10, anchor="nw")
        u.place(x=52, y=30, anchor="nw")
    fr, ic, t = s.tog
    fr.configure(width=50 if c else 226, height=44)
    fr.pack_configure(fill="none" if c else "x", padx=0 if c else 12)
    if c:
      t.place_forget()
      ic.place(relx=.5, x=0, rely=.5, anchor="center")
    else:
      ic.place(relx=0, x=26, rely=.5, anchor="center")
      t.place(x=52, rely=.5, anchor="w")

  def nav_hover(s, key, on, fr=None, title="", sub=""):
    if s.tip_job is not None:
      s.after_cancel(s.tip_job)
      s.tip_job = None
    if s.tip is not None:
      s.tip.destroy()
      s.tip = None
    f, ic = s.navs[key][:2]
    if s.cur != key:
      s.nav_fade(key, "#140e24" if on else SIDE, "#d8b4fe" if on else MUTED)
    if on and s.collapsed:
      s.tip_job = s.after(250, lambda: s.show_tip(fr, title, sub))

  def nav_fade(s, key, bg, icol, dur=0.12):
    f, ic = s.navs[key][:2]
    st = s.navfade.setdefault(key, {"bg": SIDE, "ic": MUTED, "job": None})
    if st["job"] is not None:
      try:
        s.after_cancel(st["job"])
      except Exception:
        pass
      st["job"] = None
    a0, b0 = st["bg"], st["ic"]
    t0 = time.perf_counter()

    def step():
      x = min(1.0, (time.perf_counter() - t0) / dur)
      t = x * x * (3 - 2 * x)
      c1, c2 = (bg, icol) if x >= 1 else (lerp(a0, bg, t), lerp(b0, icol, t))
      if (c1, c2) != (st["bg"], st["ic"]):
        try:
          f.configure(fg_color=c1)
          ic.configure(text_color=c2)
        except tk.TclError:
          st["job"] = None
          return
        st["bg"], st["ic"] = c1, c2
      st["job"] = s.after(10, step) if x < 1 else None
    step()

  def nav_sync(s, key, bg, icol):
    st = s.navfade.setdefault(key, {"bg": bg, "ic": icol, "job": None})
    if st["job"] is not None:
      try:
        s.after_cancel(st["job"])
      except Exception:
        pass
    st["bg"], st["ic"], st["job"] = bg, icol, None

  def show_tip(s, fr, title, sub):
    s.tip_job = None
    if s.tip is not None:
      s.tip.destroy()
    tp = tk.Toplevel(s)
    tp.overrideredirect(True)
    tp.attributes("-topmost", True)
    box = tk.Frame(tp, bg="#1a1230", highlightthickness=1, highlightbackground="#7c3aed")
    box.pack()
    tk.Label(box, text=title, bg="#1a1230", fg="white", font=(FONT_SB, 10),
         anchor="w").pack(fill="x", padx=14, pady=(8, 0))
    tk.Label(box, text=sub, bg="#1a1230", fg=MUTED, font=(FONT, 9),
         anchor="w").pack(fill="x", padx=14, pady=(0, 8))
    tp.update_idletasks()
    x = fr.winfo_rootx() + fr.winfo_width() + 10
    y = fr.winfo_rooty() + (fr.winfo_height() - tp.winfo_height()) // 2
    tp.geometry(f"+{x}+{y}")
    s.tip = tp

  def show(s, key):
    if key not in s.pages:
      s.builders[key]()
    prev = s.cur
    if prev == key and s.pages[key].winfo_ismapped():
      return
    s.cur = key
    if key in s.scs and s.order.get(key):
      bw = s.body.winfo_width()
      if bw > 300:
        s.relayout(key, False, W=bw - int(24 * s.sc_f))
    if prev in s.pages and prev != key:
      s.pages[prev].pack_forget()
    s.pages[key].pack(fill="both", expand=True)
    for k in (list(s.navs) if prev is None else {prev, key}):
      f, ic, t, u = s.navs[k]
      on = k == key
      s.nav_sync(k, "#21143d" if on else SIDE, "#c084fc" if on else MUTED)
      f.configure(fg_color="#21143d" if on else SIDE, border_color="#7c3aed" if on else SIDE)
      ic.configure(text_color="#c084fc" if on else MUTED)
      t.configure(text_color="white" if on else TXT)
    if key == "dashboard":
      s.refresh_stats()

  def log(s, msg):
    s.logbox.configure(state="normal")
    s.logbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    s.logbox.see("end")
    s.logbox.configure(state="disabled")
    s.toast(msg)

  def toast(s, msg):
    if s.toast_w is None:
      s.toast_w = ctk.CTkFrame(s, corner_radius=20, fg_color="#1a1230", border_width=1, border_color="#7c3aed")
      s.toast_lbl = ctk.CTkLabel(s.toast_w, text="", font=F(12), text_color="white")
      s.toast_lbl.pack(padx=18, pady=10)
    s.toast_lbl.configure(text=msg)
    s.toast_w.place(relx=1.0, rely=1.0, x=-26, y=-10, anchor="se")
    s.toast_w.lift()

    if getattr(s, "rise_job", None) is not None:
      try:
        s.after_cancel(s.rise_job)
      except Exception:
        pass
      s.rise_job = None

    def rise(i=1):
      try:
        t = 1 - (1 - i / 6) ** 3
        s.toast_w.place_configure(y=int(-10 - 16 * t))
      except Exception:
        s.rise_job = None
        return
      s.rise_job = s.after(16, rise, i + 1) if i < 6 else None
    rise()
    if s.toast_job is not None:
      s.after_cancel(s.toast_job)
    s.toast_job = s.after(2600, s.toast_w.place_forget)

  def page(s, key, title, sub):
    f = ctk.CTkFrame(s.body, fg_color=BG, corner_radius=0)
    s.pages[key] = f
    ctk.CTkLabel(f, text=title, font=F(28, "bold"), text_color="white").pack(anchor="w")
    ctk.CTkLabel(f, text=sub, font=F(13), text_color=MUTED).pack(anchor="w", pady=(0, 16))
    return f

  def card(s, parent):
    return ctk.CTkFrame(parent, corner_radius=14, fg_color=CARD, border_width=1, border_color=BORDER)

  def count(s, lbl, end, fmt, i=0, n=14):
    p = 1 - (1 - (i + 1) / n) ** 3
    lbl.configure(text=fmt.format(end * p))
    if i + 1 < n:
      s.after(18, lambda: s.count(lbl, end, fmt, i + 1, n))

  def build_dashboard(s):
    f = s.page("dashboard", "Dashboard", "Rig overview · one-click tuning")
    row = ctk.CTkFrame(f, fg_color=BG)
    row.pack(fill="x")
    for i, (key, title) in enumerate([("active", "TWEAKS ACTIVE"), ("hz", "MONITOR REFRESH"),
                     ("ram", "FREE RAM"), ("games", "GAMES IN LIBRARY")]):
      c = s.card(row)
      c.grid(row=0, column=i, sticky="nsew", padx=6)
      row.columnconfigure(i, weight=1, uniform="a")
      ctk.CTkLabel(c, text=title, font=F(10, "bold"), text_color=MUTED).pack(anchor="w", padx=18, pady=(16, 0))
      v = ctk.CTkLabel(c, text="-", font=F(30, "bold"), text_color="white")
      v.pack(anchor="w", padx=18)
      sub = ctk.CTkLabel(c, text="", font=F(11), text_color=MUTED)
      sub.pack(anchor="w", padx=18, pady=(0, 16))
      s.stat[key] = (v, sub)

    act = s.card(f)
    act.pack(fill="x", pady=14, padx=6)
    ctk.CTkLabel(act, text="One-click optimization", font=F(16, "bold"), text_color="white").pack(anchor="w", padx=22, pady=(18, 2))
    ctk.CTkLabel(act, text="Apply all Custom recommended tweaks, fix lagging apps, or revert everything.",
           font=F(12), text_color=MUTED).pack(anchor="w", padx=22)
    br = ctk.CTkFrame(act, fg_color=CARD)
    br.pack(fill="x", padx=22, pady=(16, 20))
    for i, (txt, sty, cmd) in enumerate([("Apply recommended", "purple", s.apply_recommended),
                       ("Fix App Lags", "green", s.fix_app_lags_now),
                       ("Max Monitor Hz", "dark", s.max_hz),
                       ("Revert everything", "red", s.revert_all)]):
      br.columnconfigure(i, weight=1, uniform="b")
      btn(br, txt, sty, cmd, 44, 13, 120).grid(row=0, column=i, sticky="ew",
                           padx=(0 if i == 0 else 6, 0 if i == 3 else 6))

    info = ctk.CTkFrame(f, fg_color=BG)
    info.pack(fill="x")
    s.hw = {}
    for i, (key, title) in enumerate([("cpu", "PROCESSOR"), ("gpu", "GRAPHICS"),
                     ("mem", "MEMORY"), ("os", "OPERATING SYSTEM")]):
      c = s.card(info)
      c.grid(row=0, column=i, sticky="nsew", padx=6)
      info.columnconfigure(i, weight=1, uniform="h")
      ctk.CTkLabel(c, text=title, font=F(10, "bold"), text_color=MUTED).pack(anchor="w", padx=18, pady=(14, 0))
      v = ctk.CTkLabel(c, text="...", font=F(12, "bold"), text_color="white",
               wraplength=170, justify="left", anchor="w")
      v.pack(anchor="w", padx=18, pady=(2, 16))
      s.hw[key] = v
    s.hw["cpu"].configure(text=cpu_name())
    s.hw["mem"].configure(text=f"{ram()[1]:.1f} GB")
    s.hw["os"].configure(text=platform.platform(terse=True))

    def fit_hw(e=None):
      sc_ = max(1.0, s.winfo_fpixels('1i') / 96)
      w = max(90, int((info.winfo_width() / 4 - 50) / sc_))
      for lb in s.hw.values():
        lb.configure(wraplength=w)
    info.bind("<Configure>", lambda e: s.deb("hw", 100, fit_hw))

    lg = s.card(f)
    lg.pack(fill="both", expand=True, pady=14, padx=6)
    ctk.CTkLabel(lg, text="Dashboard activity", font=F(15, "bold"), text_color="white").pack(anchor="w", padx=22, pady=(16, 4))
    s.logbox = ctk.CTkTextbox(lg, height=90, fg_color=CARD, text_color="#c084fc", border_width=0,
                 font=ctk.CTkFont("Consolas", 12))
    s.logbox.pack(fill="both", expand=True, padx=16, pady=(0, 14))
    s.logbox.configure(state="disabled")

  def refresh_stats(s):
    n = len(s.d["applied"])
    free, total = ram()
    s.count(s.stat["active"][0], n, "{:.0f}")
    s.count(s.stat["hz"][0], refresh_rate(), "{:.0f} Hz")
    s.count(s.stat["ram"][0], free, "{:.1f} GB")
    s.count(s.stat["games"][0], len(s.d["games"]), "{:.0f}")
    s.stat["active"][1].configure(text=f"{len(TWEAKS) - n} available")
    s.stat["hz"][1].configure(text="active display rate")
    s.stat["ram"][1].configure(text=f"of {total:.1f} GB total")
    s.stat["games"][1].configure(text="saved in library")

  def max_hz(s):
    r = set_max_hz()
    if r is None:
      s.log("Could not change refresh rate.")
    elif r[0] == r[1]:
      s.log(f"Already at max: {r[1]} Hz ({r[2]}x{r[3]})")
    else:
      s.log(f"Locked monitor to {r[1]} Hz ({r[2]}x{r[3]})")
    s.after(1500, s.refresh_stats)

  def plan(s):
    ids, notes = set(REC), []
    gpu = s.gpu_txt or gpu_name()
    modern = sys.getwindowsversion().build >= 19041
    if modern and any(k in gpu.upper() for k in ("NVIDIA", "GEFORCE", "AMD", "RADEON")):
      ids.add("hags")
    else:
      notes.append("Hardware GPU scheduling skipped (GPU or Windows version not suited)")
    if is_desktop():
      ids.add("power")
    else:
      notes.append("High performance power plan skipped (battery detected)")
    return [t for t in TWEAKS if t["id"] in ids], notes

  def apply_recommended(s, page=None):
    tw, notes = s.plan()
    if page:
      tw = [t for t in tw if t["page"] == page]
      notes = []
    tw = [t for t in tw if t["id"] not in s.d["applied"]]
    if not tw:
      s.log("Recommended tweaks are already applied.")
      return
    need = [t for t in tw if t.get("admin") and not is_admin()]
    if need:
      r = messagebox.askyesnocancel(
        APP, f"{len(tw)} recommended tweaks found for your PC, {len(need)} of them need administrator rights.\n\n"
           "Yes: restart as administrator and apply everything\n"
           f"No: apply the other {len(tw) - len(need)} now\n"
           "Cancel: do nothing")
      if r is None:
        return
      if r:
        if s.relaunch_admin():
          return
        s.log("Administrator restart was cancelled.")
        return
      tw = [t for t in tw if t not in need]
    elif not messagebox.askyesno(APP, f"Apply {len(tw)} recommended tweaks for your PC?\nAll of them can be reverted."):
      return
    s.backup_for(tw)
    done = 0
    for t in tw:
      try:
        apply_tweak(t, s.d)
        s.log(f"Applied: {t['name']}")
        done += 1
      except Exception as e:
        s.log(f"ERROR {t['name']}: {e}")
    for n in notes:
      s.log(n)
    s.clean()
    s.flush_dns()
    save(s.d)
    s.refresh_stats()
    s.refresh_cards()
    s.log(f"Recommended set applied: {done} tweaks. Restart for all changes to take effect.")

  def relaunch_admin(s):
    params = f'"{os.path.abspath(sys.argv[0])}" --recommended'
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
      pw = exe[:-10] + "pythonw.exe"
      if os.path.exists(pw):
        exe = pw
    if ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1) > 32:
      s.destroy()
      return True
    return False

  def revert_all(s):
    if not messagebox.askyesno(APP, "Revert all tweaks?"):
      return
    for t in TWEAKS:
      if t["id"] in s.d["applied"]:
        try:
          revert_tweak(t, s.d)
          s.log(f"Reverted: {t['name']}")
        except Exception as e:
          s.log(f"ERROR {t['name']}: {e}")
    save(s.d)
    s.refresh_stats()
    s.refresh_cards()

  def build_monitor(s):
    f = s.page("monitor", "Monitor", "Live CPU, RAM and GPU load")
    g = ctk.CTkFrame(f, fg_color=BG)
    g.pack(fill="both", expand=True)
    g.columnconfigure(0, weight=3)
    g.columnconfigure(1, weight=1)
    g.rowconfigure(1, weight=1)
    pc = s.card(g)
    pc.grid(row=0, column=0, sticky="nsew", padx=6, pady=(0, 10))
    ctk.CTkLabel(pc, text="THIS PC", font=F(10, "bold"), text_color=MUTED).pack(anchor="w", padx=20, pady=(14, 6))
    for k, v in (("CPU", cpu_name()), ("GPU", s.gpu_txt or "..."), ("RAM", f"{ram()[1]:.0f} GB")):
      r = ctk.CTkFrame(pc, fg_color=CARD)
      r.pack(fill="x", padx=20, pady=1)
      ctk.CTkLabel(r, text=k, width=50, anchor="w", font=F(12), text_color=MUTED).pack(side="left")
      l = ctk.CTkLabel(r, text=v, anchor="w", font=F(12), text_color="white")
      l.pack(side="left")
      if k == "GPU":
        s.mon_gpu = l
    ctk.CTkLabel(pc, text="", height=8).pack()

    ch = s.card(g)
    ch.grid(row=1, column=0, sticky="nsew", padx=6)
    top = ctk.CTkFrame(ch, fg_color=CARD)
    top.pack(fill="x", padx=20, pady=(16, 0))
    s.seg = ctk.CTkSegmentedButton(top, values=["CPU", "RAM", "GPU"], command=s.set_tab, font=F(12, "bold"),
                    selected_color="#5b21b6", selected_hover_color="#6d28d9",
                    unselected_color="#181129", unselected_hover_color="#281c45",
                    fg_color="#181129", corner_radius=16, height=32)
    s.seg.set("CPU")
    s.seg.pack(side="left")
    s.big = ctk.CTkLabel(top, text="0 %", font=F(30, "bold"), text_color="#c084fc")
    s.big.pack(side="right")
    s.cap = ctk.CTkLabel(ch, text="CPU LOAD", font=F(10, "bold"), text_color=MUTED)
    s.cap.pack(anchor="w", padx=20, pady=(4, 0))
    s.cv = tk.Canvas(ch, bg=CARD, highlightthickness=0, height=240)
    s.cv.pack(fill="both", expand=True, padx=20, pady=(4, 18))

    rc = ctk.CTkFrame(g, fg_color=BG)
    rc.grid(row=0, column=1, rowspan=2, sticky="new", padx=6)
    s.side = {}
    for k, t in (("temp", "GPU TEMP"), ("ping", "NETWORK PING"), ("status", "CPU · RAM")):
      c = s.card(rc)
      c.pack(fill="x", pady=(0, 10))
      ctk.CTkLabel(c, text=t, font=F(10, "bold"), text_color=MUTED).pack(anchor="w", padx=18, pady=(14, 0))
      v = ctk.CTkLabel(c, text="-", font=F(26, "bold"), text_color="#c084fc")
      v.pack(anchor="w", padx=18, pady=(0, 4 if k == "ping" else 16))
      if k == "ping":
        ctk.CTkLabel(c, text=f"to {PING_HOST}", font=F(11), text_color=MUTED).pack(anchor="w", padx=18, pady=(0, 14))
      s.side[k] = v

  def start_monitor(s):
    threading.Thread(target=s.slow_loop, daemon=True).start()
    s.tick_t, s._big_txt = 0.0, ""
    s.tick()
    s.anim()

  def anim(s):
    if s.cur == "monitor" and "monitor" in s.pages and not s.hidden:
      try:
        s.draw()
      except Exception:
        pass
      s.after(25, s.anim)
    else:
      s.after(400, s.anim)

  def slow_loop(s):
    smi = True
    while True:
      if s.cur != "monitor" or s.hidden:
        time.sleep(1.5)
        continue
      if smi:
        try:
          out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, creationflags=0x08000000).stdout
          r = out.strip().splitlines()[0].split(",")
          s.slow["gpu"], s.slow["temp"] = int(r[0]), int(r[1])
        except FileNotFoundError:
          smi = False
          s.slow["gpu"] = s.slow["temp"] = None
        except Exception:
          s.slow["gpu"] = s.slow["temp"] = None
      try:
        t0 = time.perf_counter()
        socket.create_connection((PING_HOST, 443), 2).close()
        s.slow["ping"] = int((time.perf_counter() - t0) * 1000)
      except Exception:
        s.slow["ping"] = None
      time.sleep(2)

  def set_tab(s, v):
    s.mtab = v
    s.cap.configure(text=f"{v} LOAD")
    s.draw()

  def tick(s):
    if s.cur != "monitor" or "monitor" not in s.pages or s.hidden:
      s.after(2500, s.tick)
      return
    sl = s.slow
    vals = {"CPU": cpu_load(), "RAM": float(ram_pct()), "GPU": float(sl["gpu"] or 0)}
    for k, v in vals.items():
      s.hist[k].append(v)
      del s.hist[k][:-60]
    s.tick_t = time.perf_counter()
    s.side["temp"].configure(text=f"{sl['temp']} °C" if sl["temp"] is not None else "N/A")
    s.side["ping"].configure(text=f"{sl['ping']} ms" if sl["ping"] is not None else "N/A")
    s.side["status"].configure(text=f"{vals['CPU']:.0f}% · {vals['RAM']:.0f}%")
    if s.cur == "monitor":
      s.draw()
    s.after(1000, s.tick)

  def draw(s):
    cv = s.cv
    cv.delete("all")
    w, h = max(cv.winfo_width(), 100), max(cv.winfo_height(), 100)
    for i in range(1, 10):
      cv.create_line(w * i / 10, 0, w * i / 10, h, fill=BORDER)
    for i in range(1, 4):
      cv.create_line(0, h * i / 4, w, h * i / 4, fill=BORDER)
    hist = s.hist[s.mtab]
    txt = f"{(hist[-1] if hist else 0):.0f} %"
    if txt != getattr(s, "_big_txt", None):
      s._big_txt = txt
      s.big.configure(text=txt)
    if len(hist) < 2:
      return
    x = min(1.0, (time.perf_counter() - getattr(s, "tick_t", 0.0)) / 1.0)
    e = 1 - (1 - x) ** 3
    n = len(hist)
    full = n >= 60
    pts = []
    for i, v in enumerate(hist):
      if i == n - 1:
        v = hist[-2] + (hist[-1] - hist[-2]) * e
        px = (i + 1 - e) if full else (i - 1 + e)
      else:
        px = (i + 1 - e) if full else i
      pts += [px * w / 59, h - 6 - (h - 12) * v / 100]
    cv.create_line(*pts, fill="#4c1d95", width=7, smooth=True, capstyle="round")
    cv.create_line(*pts, fill="#a855f7", width=2, smooth=True)
    px, py = pts[-2], pts[-1]
    cv.create_oval(px - 4, py - 4, px + 4, py + 4, fill="#0d0914", outline="#c084fc", width=2)

  def build_booster(s):
    f = s.page("booster", "Games & App Lag", "Launch games at high priority and clear stuck/lagging apps")
    s.glist = SmoothScroll(f, height=280, corner_radius=14, fg_color=CARD,
                     border_width=1, border_color=BORDER)
    s.glist.pack(fill="x", pady=(0, 14), padx=6)
    bar = ctk.CTkFrame(f, fg_color=BG)
    bar.pack(anchor="w", padx=6)
    btn(bar, "Add game (.exe)", "purple", s.add_game).pack(side="left", padx=(0, 10))
    btn(bar, "Launch with high priority", "green", s.launch).pack(side="left", padx=10)
    btn(bar, "Kill Hung Apps", "red", s.fix_app_lags_now).pack(side="left", padx=10)
    btn(bar, "Remove", "dark", s.remove_game).pack(side="left", padx=10)
    s.draw_games()

  def draw_games(s):
    for w in s.glist.winfo_children():
      w.destroy()
    if not s.d["games"]:
      ctk.CTkLabel(s.glist, text="No games yet. Click “Add game (.exe)”.", text_color=MUTED,
             font=F(12)).pack(pady=20)
    for i, g in enumerate(s.d["games"]):
      on = i == s.sel
      ctk.CTkButton(s.glist, text=f" {os.path.basename(g)}  —  {g}", anchor="w", height=42,
             corner_radius=21, font=F(12), text_color=TXT,
             fg_color="#21143d" if on else "transparent", hover_color="#281c45",
             command=lambda i=i: s.pick(i)).pack(fill="x", pady=2)

  def pick(s, i):
    s.sel = i
    s.draw_games()

  def add_game(s):
    p = filedialog.askopenfilename(filetypes=[("Programs", "*.exe")])
    if p and p not in s.d["games"]:
      s.d["games"].append(p)
      save(s.d)
      s.draw_games()
      s.log(f"Added game: {os.path.basename(p)}")

  def remove_game(s):
    if s.sel is not None and s.sel < len(s.d["games"]):
      s.d["games"].pop(s.sel)
      s.sel = None
      save(s.d)
      s.draw_games()

  def launch(s):
    if s.sel is None or s.sel >= len(s.d["games"]):
      messagebox.showinfo(APP, "Select a game from the list first.")
      return
    p = s.d["games"][s.sel]
    try:
      subprocess.Popen([p], cwd=os.path.dirname(p), creationflags=0x00000080)
      s.log(f"Launched with high priority: {os.path.basename(p)}")
    except Exception as e:
      s.log(f"ERROR launching: {e}")

  def tweak_page(s, key, title, sub):
    f = ctk.CTkFrame(s.body, fg_color=BG, corner_radius=0)
    s.pages[key] = f
    head = ctk.CTkFrame(f, fg_color=BG)
    head.pack(fill="x", pady=(0, 10))
    ctk.CTkLabel(head, text=title, font=F(28, "bold"), text_color="white").pack(anchor="w")
    ctk.CTkLabel(head, text=sub, font=F(13), text_color=MUTED).pack(anchor="w")
    tb = ctk.CTkFrame(f, fg_color=BG)
    tb.pack(fill="x", pady=(0, 12))
    ab = btn(tb, "Apply Selected (0)", "purple", lambda: s.run_sel(key, True), 38, 12, 170)
    ab.pack(side="left", padx=(0, 8))
    s.applybtn[key] = ab
    btn(tb, "Apply Recommended", "dark", lambda: s.apply_recommended(key), 38, 12, 170).pack(side="left", padx=8)
    btn(tb, "Revert Selected", "dark", lambda: s.run_sel(key, False), 38, 12, 150).pack(side="left", padx=8)
    btn(tb, "Revert Recommended", "dark", lambda: s.revert_recommended(key), 38, 12, 170).pack(side="left", padx=8)

    sec = ctk.CTkFrame(f, fg_color=BG)
    sec.pack(fill="x", pady=(2, 8))
    logo = ctk.CTkFrame(sec, width=36, height=36, corner_radius=18, fg_color="#28164a",
              border_width=1, border_color="#6d28d9")
    logo.pack(side="left")
    logo.pack_propagate(False)
    ctk.CTkLabel(logo, text="\uE945", font=ctk.CTkFont(ICON_FONT, size=16),
           text_color="#c084fc").place(relx=.5, rely=.5, anchor="center")
    tf = ctk.CTkFrame(sec, fg_color=BG)
    tf.pack(side="left", padx=12)
    ctk.CTkLabel(tf, text=SECTION.get(key, title), font=F(16, "bold"), text_color="white").pack(anchor="w")
    if key in SECTION_SUB:
      ctk.CTkLabel(tf, text=SECTION_SUB[key], font=F(11), text_color=MUTED).pack(anchor="w")

    sc = SmoothScroll(f, fg_color=BG, corner_radius=0)
    sc.pack(fill="both", expand=True)
    s.scs[key], s.order[key] = sc, []
    s.switches[key], s.cards[key] = {}, {}
    s.sc_f = max(1.0, s.winfo_fpixels('1i') / 96)
    s.wraps[key] = (int(230 * s.sc_f), int(170 * s.sc_f))
    if not hasattr(s, "fn_name"):
      k = s.sc_f
      s.fn_name = tkf.Font(family=FONT_SB, size=-round(14 * k))
      s.fn_desc = tkf.Font(family=FONT, size=-round(12 * k))
      s.fn_icon = tkf.Font(family="Segoe UI Symbol", size=-round(21 * k))
      s.fn_warn = tkf.Font(family="Segoe UI Symbol", size=-round(14 * k))
    todo = [t for t in TWEAKS if t["page"] == key]

    def batch(i=0):
      for t in todo[i:i + 6]:
        s.make_card(sc, key, t)
      if s.cur == key or i + 6 >= len(todo):
        s.relayout(key, True)
      if i + 6 < len(todo):
        s.after(10, lambda: batch(i + 6))
    batch()
    sc.bind("<Configure>", lambda e: s.deb("rl_" + key, 120, lambda: s.relayout(key)))

  def relayout(s, key, force=False, W=None):
    sc = s.scs.get(key)
    if sc is None or not s.order.get(key):
      return
    f = s.sc_f
    W = W or sc.winfo_width()
    if W < 100:
      W = int(900 * f)
    usable = W - 22 * f
    cols = max(1, min(3, int(usable // (300 * f))))
    cw = usable / cols - 12 * f
    sig = (cols, int(cw // 10), len(s.order[key]))
    if not force and s.lay.get(key) == sig:
      return
    s.lay[key] = sig
    wd, wn = max(120, int(cw - 66 * f)), max(90, int(cw - 160 * f))
    s.wraps[key] = (wd, wn)
    for j in range(3):
      sc.columnconfigure(j, weight=1 if j < cols else 0, uniform="c" if j < cols else "")
    for idx, card in enumerate(s.order[key]):
      card.grid(row=idx // cols, column=idx % cols, sticky="nsew", padx=6, pady=6)
    for c in s.cards[key].values():
      c[4][1].configure(wraplength=wn)
      c[4][3].configure(wraplength=wd)

  def make_card(s, sc, key, t):
    wd, wn = s.wraps[key]
    card = tk.Frame(sc, bg=CARD, bd=0, highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=BORDER)
    card.columnconfigure(1, weight=1)
    card.rowconfigure(1, weight=1)
    cv = tk.Label(card, text="○", font=s.fn_icon, fg="#6e5c8a", bg=CARD, bd=0)
    cv.grid(row=0, column=0, padx=(14, 8), pady=(8, 0), sticky="n")
    name = tk.Label(card, text=t["name"], font=s.fn_name, fg=TXT, bg=CARD,
            anchor="w", justify="left", wraplength=wn, bd=0)
    name.grid(row=0, column=1, sticky="w", pady=(14, 0))
    fg, bgc = RISK[t.get("risk", "low")]
    rb = tk.Frame(card, bg=CARD)
    rb.grid(row=0, column=2, sticky="ne", padx=(6, 14), pady=(14, 0))
    extra = []
    if t.get("warn"):
      wl = tk.Label(rb, text="\u26a0", font=s.fn_warn, fg="#fbbf24", bg=CARD, bd=0)
      wl.pack(side="left", padx=(0, 6))
      extra.append(wl)
    pls = []
    rp = pill(rb, t.get("risk", "low").upper(), fg, bgc)
    rp.pack(side="left")
    pls.append(rp)
    desc = tk.Label(card, text=t["desc"], font=s.fn_desc, fg=MUTED, bg=CARD, anchor="nw",
            justify="left", wraplength=wd, bd=0)
    desc.grid(row=1, column=1, columnspan=2, sticky="nw", padx=(0, 14), pady=(6, 0))
    tags = tk.Frame(card, bg=CARD)
    tags.grid(row=2, column=1, columnspan=2, sticky="w", pady=(8, 14))
    active = pill(tags, "ACTIVE", "#34d399", "#10261f")
    pls.append(active)
    if t["id"] in REC:
      rc = pill(tags, "RECOMMENDED", "#d8b4fe", "#2e1065")
      rc.pack(side="left", padx=(0, 6))
      pls.append(rc)
    if t.get("admin"):
      ad = pill(tags, "ADMIN", "#e9d5ff", "#2a1f3d")
      ad.pack(side="left", padx=(0, 6))
      pls.append(ad)
    s.pills[(key, t["id"])] = pls
    v = ctk.BooleanVar(value=False)
    s.switches[key][t["id"]] = v
    s.cards[key][t["id"]] = (card, v, cv, active, [cv, name, rb, desc, tags] + extra)
    s.order[key].append(card)
    v.trace_add("write", lambda *a, k=key, tid=t["id"]: (s.card_vis(k, tid), s.upd_count(k)))

    def leave(e, card=card, tid=t["id"]):
      try:
        w = card.winfo_containing(e.x_root, e.y_root)
      except Exception:
        w = None
      if w is not None and str(w).startswith(str(card)):
        return
      s.card_vis(key, tid)
    for w in (card, cv, name, desc, tags, rb):
      w.bind("<Button-1>", lambda e, v=v: v.set(not v.get()))
      w.bind("<Enter>", lambda e, tid=t["id"]: s.card_vis(key, tid, True))
    card.bind("<Leave>", leave)
    s.card_vis(key, t["id"])

  def card_vis(s, key, tid, hover=False):
    card, v, cv, active, bgw = s.cards[key][tid]
    on = v.get()
    col = "#21143d" if on else ("#1c1430" if hover else CARD)
    bd = PURPLE if on else ("#4c337a" if hover else BORDER)
    cv.configure(text="\u25c9" if on else "\u25cb", fg="#c084fc" if on else "#6e5c8a")
    if tid in s.d["applied"]:
      active.pack(side="left", padx=(0, 6))
    else:
      active.pack_forget()
    s.fade(key, tid, col, bd)

  def paint_card(s, key, tid, col, bd):
    card, v, cv, active, bgw = s.cards[key][tid]
    card.configure(bg=col, highlightbackground=bd, highlightcolor=bd)
    for w in bgw:
      w.configure(bg=col)
    for p in s.pills.get((key, tid), ()):
      p.configure(bg_color=col)

  def fade(s, key, tid, col, bd, dur=0.14):
    """Kart rengini/cercevesini zaman tabanli smoothstep ile yumusak degistirir."""
    st = s.fades.setdefault((key, tid), {"bg": CARD, "bd": BORDER, "job": None})
    if st["job"] is not None:
      try:
        s.after_cancel(st["job"])
      except Exception:
        pass
      st["job"] = None
    a0, b0 = st["bg"], st["bd"]
    if (a0, b0) == (col, bd):
      return
    t0 = time.perf_counter()

    def step():
      x = min(1.0, (time.perf_counter() - t0) / dur)
      t = x * x * (3 - 2 * x)
      c1, c2 = (col, bd) if x >= 1 else (lerp(a0, col, t), lerp(b0, bd, t))
      if (c1, c2) != (st["bg"], st["bd"]):
        try:
          s.paint_card(key, tid, c1, c2)
        except tk.TclError:
          st["job"] = None
          return
        st["bg"], st["bd"] = c1, c2
      st["job"] = s.after(10, step) if x < 1 else None
    step()

  def upd_count(s, key):
    n = sum(1 for tid, c in s.cards[key].items() if c[1].get() and tid not in s.d["applied"])
    s.applybtn[key].configure(text=f"Apply Selected ({n})")

  def refresh_cards(s):
    for key, cards in s.cards.items():
      for tid, c in cards.items():
        c[1].set(False)
        s.card_vis(key, tid)
      s.upd_count(key)

  def run_sel(s, key, apply):
    todo = [t for t in TWEAKS if t["page"] == key and t["id"] in s.switches[key] and s.switches[key][t["id"]].get()
        and apply != (t["id"] in s.d["applied"])]
    risky = [t["name"] for t in todo if apply and t.get("risk") in ("high", "crit")]
    if risky and not messagebox.askyesno(
        APP, "These tweaks are high risk:\n\n" + "\n".join(" - " + n for n in risky) +
        "\n\nThey can reduce security or change system behavior. All of them can be reverted.\nApply anyway?"):
      return
    if apply and todo:
      s.backup_for(todo)
    for t in todo:
      try:
        (apply_tweak if apply else revert_tweak)(t, s.d)
        s.log(("Applied: " if apply else "Reverted: ") + t["name"])
      except Exception as e:
        s.log(f"ERROR {t['name']}: {e}")
    save(s.d)
    s.refresh_cards()
    s.refresh_stats()

  def revert_recommended(s, page=None):
    done = 0
    for t in TWEAKS:
      if (t["id"] in REC or t["id"] in ("hags", "power")) and t["id"] in s.d["applied"] \
          and (page is None or t["page"] == page):
        try:
          revert_tweak(t, s.d)
          s.log(f"Reverted: {t['name']}")
          done += 1
        except Exception as e:
          s.log(f"ERROR {t['name']}: {e}")
    if not done:
      s.log("No recommended tweaks to revert.")
    save(s.d)
    s.refresh_cards()
    s.refresh_stats()


import sys as _sys
if _sys.platform == "win32":
  try:
    import ctypes as _ct
    _hwnd = _ct.windll.kernel32.GetConsoleWindow()
    if _hwnd:
      _ct.windll.user32.ShowWindow(_hwnd, 0)
  except Exception:
    pass

if __name__ == "__main__":
  try:
    app = App()
    if "--recommended" in sys.argv:
      app.after(900, app.apply_recommended)
    app.mainloop()
  except Exception:
    import traceback
    err = traceback.format_exc()
    try:
      with open(os.path.join(DIR, "crash.log"), "w", encoding="utf-8") as fh:
        fh.write(err)
    except Exception:
      pass
    try:
      messagebox.showerror(APP, "Stormy Tweaks could not start:\n\n" + err[-1500:])
    except Exception:
      pass
