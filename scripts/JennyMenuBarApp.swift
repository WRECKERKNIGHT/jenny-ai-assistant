import Cocoa
import WebKit

let SERVER_URL = "http://localhost:3005"
let MINI_URL = "\(SERVER_URL)/mini.html"
let HEALTH_CHECK_INTERVAL: TimeInterval = 3.0
let HEALTH_CHECK_TIMEOUT: TimeInterval = 2.0

func loadingHTML(status: String = "Connecting to JENNY server...") -> String {
    return """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
    <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
        background: #000000; color: #fff;
        font-family: 'Orbitron', -apple-system, BlinkMacSystemFont, sans-serif;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        height: 100vh; overflow: hidden;
    }
    .loader {
        width: 60px; height: 60px; border-radius: 50%;
        border: 2px solid rgba(255,215,0,0.15); border-top-color: #ffd700;
        animation: spin 1s linear infinite; margin-bottom: 20px; position: relative;
    }
    .loader::after {
        content: ''; position: absolute; inset: 6px; border-radius: 50%;
        border: 2px solid rgba(255,255,255,0.15); border-bottom-color: #ffffff;
        animation: spin 1.5s linear infinite reverse;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .title {
        font-size: 16px; font-weight: 900; letter-spacing: 5px;
        background: linear-gradient(90deg, #ffd700, #ffffff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px;
    }
    .status { font-size: 9px; color: rgba(255,255,255,0.5); letter-spacing: 1px; text-transform: uppercase; }
    .retry-btn {
        margin-top: 20px; padding: 8px 20px; background: rgba(255,215,0,0.1);
        border: 1px solid rgba(255,215,0,0.3); border-radius: 8px; color: #ffd700;
        font-family: inherit; font-size: 10px; letter-spacing: 1px; cursor: pointer;
        transition: all 0.2s ease;
    }
    .retry-btn:hover { background: rgba(255,215,0,0.2); border-color: #ffd700; }
    .dot { display:inline-block; width:6px; height:6px; border-radius:50%; background:#ff3b30; margin-right:6px; animation: blink 1.5s ease-in-out infinite; }
    @keyframes blink { 0%,100%{opacity:0.3;} 50%{opacity:1;} }
    </style>
    </head>
    <body>
    <div class="loader"></div>
    <div class="title">JENNY</div>
    <div class="status"><span class="dot"></span>\(status)</div>
    <button class="retry-btn" onclick="window.webkit.messageHandlers.retry.postMessage('retry')">RETRY</button>
    </body>
    </html>
    """
}

class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKScriptMessageHandler {
    var statusItem: NSStatusItem!
    var popover: NSPopover!
    var webView: WKWebView!
    var eventMonitor: Any?
    var serverOnline = false
    var healthTimer: Timer?
    var serverMenuItem = NSMenuItem(title: "  ● Checking server...", action: nil, keyEquivalent: "")
    var statusMenuItem = NSMenuItem(title: "  Status: Starting", action: nil, keyEquivalent: "")

    func applicationDidFinishLaunching(_ aNotification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "brain.head.profile", accessibilityDescription: "JENNY")
            button.image?.isTemplate = true
            button.action = #selector(statusBarButtonClicked(_:))
            button.target = self
        }
        setupPopover()
        constructMenu()
        startHealthCheck()
        print("[JENNY MenuBar] Initialized")
    }

    func setupPopover() {
        popover = NSPopover()
        popover.contentSize = NSSize(width: 460, height: 680)
        popover.behavior = .transient
        popover.animates = true
        popover.appearance = NSAppearance(named: .darkAqua)

        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        config.userContentController.add(self, name: "retry")
        config.userContentController.add(self, name: "openDesktopApp")
        config.userContentController.add(self, name: "openFullApp")

        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 460, height: 680), configuration: config)
        webView.navigationDelegate = self
        webView.setValue(false, forKey: "drawsBackground")
        webView.loadHTMLString(loadingHTML(), baseURL: nil)

        let viewController = NSViewController()
        viewController.view = webView
        popover.contentViewController = viewController

        eventMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown, .rightMouseDown]) { [weak self] _ in
            if let popover = self?.popover, popover.isShown { popover.performClose(nil) }
        }
    }

    func constructMenu() {
        let menu = NSMenu()
        menu.autoenablesItems = false

        menu.addItem(NSMenuItem(title: "  J.E.N.N.Y. Neural Assistant", action: nil, keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())

        serverMenuItem.isEnabled = false
        menu.addItem(serverMenuItem)

        statusMenuItem.isEnabled = false
        menu.addItem(statusMenuItem)
        menu.addItem(NSMenuItem.separator())

        let miniItem = NSMenuItem(title: "  Open Mini HUD", action: #selector(togglePopover(_:)), keyEquivalent: "j")
        miniItem.target = self
        menu.addItem(miniItem)

        let micItem = NSMenuItem(title: "  Toggle Microphone", action: #selector(toggleMic), keyEquivalent: "m")
        micItem.target = self
        menu.addItem(micItem)

        let mainItem = NSMenuItem(title: "  Open Main Interface", action: #selector(openMainApp), keyEquivalent: "o")
        mainItem.target = self
        menu.addItem(mainItem)
        menu.addItem(NSMenuItem.separator())

        let weatherItem = NSMenuItem(title: "  Quick Weather", action: #selector(quickWeather), keyEquivalent: "w")
        weatherItem.target = self
        menu.addItem(weatherItem)

        let systemItem = NSMenuItem(title: "  System Status", action: #selector(quickSystem), keyEquivalent: "s")
        systemItem.target = self
        menu.addItem(systemItem)
        menu.addItem(NSMenuItem.separator())

        let refreshItem = NSMenuItem(title: "  Refresh Connection", action: #selector(refreshConnection), keyEquivalent: "r")
        refreshItem.target = self
        menu.addItem(refreshItem)

        let startServerItem = NSMenuItem(title: "  Start Server", action: #selector(startServer), keyEquivalent: "n")
        startServerItem.target = self
        menu.addItem(startServerItem)
        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "  Quit JENNY", action: #selector(quitApp), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    func startHealthCheck() {
        checkServer()
        healthTimer = Timer.scheduledTimer(withTimeInterval: HEALTH_CHECK_INTERVAL, repeats: true) { [weak self] _ in
            self?.checkServer()
        }
    }

    func checkServer() {
        guard let url = URL(string: "\(SERVER_URL)/api/system-status?t=\(Int(Date().timeIntervalSince1970))") else { return }
        var request = URLRequest(url: url)
        request.timeoutInterval = HEALTH_CHECK_TIMEOUT
        let task = URLSession.shared.dataTask(with: request) { [weak self] _, response, error in
            let online = error == nil && (response as? HTTPURLResponse)?.statusCode == 200
            DispatchQueue.main.async { self?.updateServerStatus(online) }
        }
        task.resume()
    }

    func updateServerStatus(_ online: Bool) {
        serverOnline = online
        serverMenuItem.title = online ? "  ● Server Online" : "  ● Server Offline"
        statusMenuItem.title = online ? "  Status: Ready" : "  Status: Starting Server..."
        if online {
            loadMiniHUD()
        } else {
            autoStartServer()
        }
    }

    func autoStartServer() {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        let appPath = Bundle.main.bundlePath
        var appDir = (appPath as NSString).deletingLastPathComponent
        if appDir.hasSuffix("/bin") {
            appDir = (appDir as NSString).deletingLastPathComponent
        }
        task.arguments = ["-c", "cd \"\(appDir)\" && node server.js &"]
        try? task.run()
    }

    func loadMiniHUD() {
        guard let url = URL(string: MINI_URL) else { return }
        let currentURL = webView.url?.absoluteString ?? ""
        if !currentURL.contains("mini.html") || !serverOnline {
            webView.load(URLRequest(url: url))
        }
    }

    @objc func statusBarButtonClicked(_ sender: Any?) { togglePopover(sender as AnyObject?) }

    @objc func togglePopover(_ sender: AnyObject?) {
        guard let button = statusItem.button else { return }
        if popover.isShown {
            popover.performClose(sender)
        } else {
            if serverOnline { loadMiniHUD() }
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            popover.contentViewController?.view.window?.makeKey()
        }
    }

    @objc func toggleMic() {
        guard let url = URL(string: "\(SERVER_URL)/api/toggle-mic") else { return }
        let task = URLSession.shared.dataTask(with: url) { [weak self] _, _, error in
            DispatchQueue.main.async {
                if error == nil { self?.togglePopover(nil) }
            }
        }
        task.resume()
    }

    @objc func openMainApp() {
        if let url = URL(string: SERVER_URL) { NSWorkspace.shared.open(url) }
    }

    @objc func quickWeather() {
        guard let url = URL(string: "\(SERVER_URL)/api/weather") else { return }
        let task = URLSession.shared.dataTask(with: url) { data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  json["success"] as? Bool == true else { return }
            let city = json["city"] as? String ?? "Unknown"
            let temp = json["tempC"] as? Int ?? 0
            let cond = json["condition"] as? String ?? "Unknown"
            DispatchQueue.main.async {
                let alert = NSAlert()
                alert.messageText = "Weather - \(city)"
                alert.informativeText = "\(temp)C, \(cond)"
                alert.alertStyle = .informational
                alert.addButton(withTitle: "OK")
                alert.runModal()
            }
        }
        task.resume()
    }

    @objc func quickSystem() {
        guard let url = URL(string: "\(SERVER_URL)/api/system-status") else { return }
        let task = URLSession.shared.dataTask(with: url) { data, _, _ in
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  json["success"] as? Bool == true else { return }
            let cpu = (json["cpu"] as? [String: Any])?["usage"] as? Int ?? 0
            let ram = (json["ram"] as? [String: Any])?["usage"] as? Int ?? 0
            let batt = (json["battery"] as? [String: Any])?["level"] as? Int ?? 0
            let uptime = json["uptime"] as? Int ?? 0
            DispatchQueue.main.async {
                let alert = NSAlert()
                alert.messageText = "System Status"
                alert.informativeText = "CPU: \(cpu)%\nRAM: \(ram)%\nBattery: \(batt)%\nUptime: \(uptime/3600)h \((uptime%3600)/60)m"
                alert.alertStyle = .informational
                alert.addButton(withTitle: "OK")
                alert.runModal()
            }
        }
        task.resume()
    }

    @objc func refreshConnection() {
        serverMenuItem.title = "  ● Checking..."
        checkServer()
    }

    @objc func startServer() {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        let appPath = Bundle.main.bundlePath
        let appDir = (appPath as NSString).deletingLastPathComponent.replacingOccurrences(of: "/bin/JennyAI.app", with: "")
        task.arguments = ["-c", "cd \"\(appDir)\" && node server.js &"]
        try? task.run()
        serverMenuItem.title = "  ● Starting server..."
    }

    @objc func quitApp() {
        if let monitor = eventMonitor { NSEvent.removeMonitor(monitor) }
        healthTimer?.invalidate()
        NSApplication.shared.terminate(nil)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        if message.name == "retry" { refreshConnection() }
        else if message.name == "openDesktopApp" || message.name == "openFullApp" {
            openDesktopApp()
        }
    }

    @objc func openDesktopApp() {
        let appBundlePath = Bundle.main.bundlePath.replacingOccurrences(of: "JennyAI.app", with: "JennyDesktop.app")
        if let url = URL(string: "file://\(appBundlePath)/Contents/MacOS/JennyDesktop") {
            NSWorkspace.shared.openApplication(at: url, configuration: NSWorkspace.OpenConfiguration())
        } else {
            openMainApp()
        }
        popover.performClose(nil)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
