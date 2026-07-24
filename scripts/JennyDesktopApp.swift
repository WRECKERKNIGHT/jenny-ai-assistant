import Cocoa
import WebKit

let SERVER_URL = "http://localhost:3005"
let HEALTH_CHECK_TIMEOUT: TimeInterval = 2.0

func desktopLoadingHTML(status: String = "Connecting to JENNY server...") -> String {
    return """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
    <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
        background: #000; color: #fff;
        font-family: 'Orbitron', -apple-system, BlinkMacSystemFont, sans-serif;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        height: 100vh; overflow: hidden;
    }
    .loader {
        width: 80px; height: 80px; border-radius: 50%;
        border: 2px solid rgba(255,215,0,0.15); border-top-color: #ffd700;
        animation: spin 1s linear infinite; margin-bottom: 24px; position: relative;
    }
    .loader::after {
        content: ''; position: absolute; inset: 8px; border-radius: 50%;
        border: 2px solid rgba(255,255,255,0.15); border-bottom-color: #ffffff;
        animation: spin 1.5s linear infinite reverse;
    }
    .loader::before {
        content: ''; position: absolute; inset: 18px; border-radius: 50%;
        border: 1.5px solid rgba(255,215,0,0.1); border-left-color: #ffd700;
        animation: spin 2s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .title {
        font-size: 32px; font-weight: 900; letter-spacing: 8px;
        background: linear-gradient(90deg, #ffd700, #ffffff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 12px;
    }
    .subtitle { font-size: 11px; color: rgba(255,255,255,0.5); letter-spacing: 2px; margin-bottom: 6px; text-transform: uppercase; }
    .status { font-size: 10px; color: rgba(255,255,255,0.4); letter-spacing: 1px; }
    .retry-btn {
        margin-top: 30px; padding: 10px 28px; background: rgba(255,215,0,0.08);
        border: 1px solid rgba(255,215,0,0.25); border-radius: 10px; color: #ffd700;
        font-family: inherit; font-size: 11px; letter-spacing: 1.5px; cursor: pointer;
        transition: all 0.2s ease;
    }
    .retry-btn:hover { background: rgba(255,215,0,0.15); border-color: #ffd700; }
    .dot { display:inline-block; width:6px; height:6px; border-radius:50%; background:#ff3b30; margin-right:6px; animation: blink 1.5s ease-in-out infinite; }
    .dot.online { background: #34c759; }
    @keyframes blink { 0%,100%{opacity:0.3;} 50%{opacity:1;} }
    </style>
    </head>
    <body>
    <div class="loader"></div>
    <div class="title">J.E.N.N.Y.</div>
    <div class="subtitle">NEURAL ASSISTANT INTERFACE</div>
    <div class="status"><span class="dot"></span>\(status)</div>
    <button class="retry-btn" onclick="window.webkit.messageHandlers.retry.postMessage('retry')">RETRY CONNECTION</button>
    </body>
    </html>
    """
}

class DesktopAppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKScriptMessageHandler, NSToolbarDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var toolbar: NSToolbar?
    var urlField: NSTextField?
    var statusLabel: NSTextField?
    var serverOnline = false
    var healthTimer: Timer?

    func setupMenuBar() {
        let mainMenu = NSMenu()
        
        let appMenu = NSMenu()
        let appName = "JENNY Desktop"
        appMenu.addItem(NSMenuItem(title: "About \(appName)", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: ""))
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(NSMenuItem(title: "Preferences...", action: nil, keyEquivalent: ","))
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(NSMenuItem(title: "Hide \(appName)", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h"))
        
        let hideOthers = NSMenuItem(title: "Hide Others", action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(hideOthers)
        appMenu.addItem(NSMenuItem(title: "Show All", action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: ""))
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(NSMenuItem(title: "Quit \(appName)", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        
        let appMenuItem = NSMenuItem()
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)
        
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(NSMenuItem(title: "Undo", action: Selector(("undo:")), keyEquivalent: "z"))
        editMenu.addItem(NSMenuItem(title: "Redo", action: Selector(("redo:")), keyEquivalent: "Z"))
        editMenu.addItem(NSMenuItem.separator())
        editMenu.addItem(NSMenuItem(title: "Cut", action: Selector(("cut:")), keyEquivalent: "x"))
        editMenu.addItem(NSMenuItem(title: "Copy", action: Selector(("copy:")), keyEquivalent: "c"))
        editMenu.addItem(NSMenuItem(title: "Paste", action: Selector(("paste:")), keyEquivalent: "v"))
        editMenu.addItem(NSMenuItem(title: "Select All", action: Selector(("selectAll:")), keyEquivalent: "a"))
        
        let editMenuItem = NSMenuItem()
        editMenuItem.submenu = editMenu
        mainMenu.addItem(editMenuItem)
        
        let viewMenu = NSMenu(title: "View")
        viewMenu.addItem(NSMenuItem(title: "Reload", action: #selector(refreshPage), keyEquivalent: "r"))
        viewMenu.addItem(NSMenuItem(title: "Toggle Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f"))
        
        let viewMenuItem = NSMenuItem()
        viewMenuItem.submenu = viewMenu
        mainMenu.addItem(viewMenuItem)
        
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(NSMenuItem(title: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m"))
        windowMenu.addItem(NSMenuItem(title: "Zoom", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: ""))
        windowMenu.addItem(NSMenuItem.separator())
        windowMenu.addItem(NSMenuItem(title: "Bring All to Front", action: #selector(NSApplication.arrangeInFront(_:)), keyEquivalent: ""))
        
        let windowMenuItem = NSMenuItem()
        windowMenuItem.submenu = windowMenu
        mainMenu.addItem(windowMenuItem)
        
        NSApplication.shared.mainMenu = mainMenu
    }

    func applicationDidFinishLaunching(_ aNotification: Notification) {
        let screenFrame = NSScreen.main?.visibleFrame ?? NSRect(x: 100, y: 100, width: 1280, height: 850)
        let width: CGFloat = min(1400, screenFrame.width * 0.85)
        let height: CGFloat = min(900, screenFrame.height * 0.9)
        let x = screenFrame.midX - width / 2
        let y = screenFrame.midY - height / 2

        window = NSWindow(contentRect: NSRect(x: x, y: y, width: width, height: height),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered, defer: false)
        window.title = "JENNY Neural Assistant"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.backgroundColor = NSColor(red: 0, green: 0, blue: 0, alpha: 1)
        window.minSize = NSSize(width: 600, height: 400)
        window.setFrameAutosaveName("JennyDesktopWindow")

        setupToolbar()
        setupMenuBar()

        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        config.userContentController.add(self, name: "retry")
        config.userContentController.add(self, name: "navBack")
        config.userContentController.add(self, name: "navForward")
        config.userContentController.add(self, name: "startServers")

        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.navigationDelegate = self
        webView.setValue(false, forKey: "drawsBackground")
        webView.autoresizingMask = [.width, .height]
        
        let appPath = Bundle.main.bundlePath
        var appDir = (appPath as NSString).deletingLastPathComponent
        if appDir.hasSuffix("/bin") {
            appDir = (appDir as NSString).deletingLastPathComponent
        }
        let offlineUrl = URL(fileURLWithPath: appDir).appendingPathComponent("public/offline.html")
        webView.loadFileURL(offlineUrl, allowingReadAccessTo: offlineUrl.deletingLastPathComponent())

        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        startHealthCheck()
        print("[JENNY Desktop] Launched")
    }

    func setupToolbar() {
        let toolbar = NSToolbar(identifier: "MainToolbar")
        toolbar.delegate = self
        toolbar.displayMode = .iconOnly
        window.toolbar = toolbar

        statusLabel = NSTextField(frame: NSRect(x: 0, y: 0, width: 120, height: 20))
        statusLabel?.isEditable = false
        statusLabel?.isBordered = false
        statusLabel?.drawsBackground = false
        statusLabel?.textColor = NSColor.secondaryLabelColor
        statusLabel?.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .medium)
        statusLabel?.stringValue = "● Connecting..."
    }

    func startHealthCheck() {
        checkServer()
        healthTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
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
        statusLabel?.stringValue = online ? "● Online" : "● Offline"
        statusLabel?.textColor = online ? NSColor.systemGreen : NSColor.systemOrange
        if online {
            loadMainUI()
        } else {
            loadOfflineUI()
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
        _ = try? task.run()
    }

    func loadMainUI() {
        guard let url = URL(string: SERVER_URL) else { return }
        let current = webView.url?.absoluteString ?? ""
        if !current.contains("localhost:3005") || current.contains("mini.html") || !serverOnline {
            webView.load(URLRequest(url: url))
        }
    }

    func loadOfflineUI() {
        let appPath = Bundle.main.bundlePath
        var appDir = (appPath as NSString).deletingLastPathComponent
        if appDir.hasSuffix("/bin") {
            appDir = (appDir as NSString).deletingLastPathComponent
        }
        let offlineUrl = URL(fileURLWithPath: appDir).appendingPathComponent("public/offline.html")
        let current = webView.url?.absoluteString ?? ""
        if !current.contains("offline.html") {
            webView.loadFileURL(offlineUrl, allowingReadAccessTo: offlineUrl.deletingLastPathComponent())
        }
    }

    @objc func refreshPage() {
        if serverOnline {
            webView.reload()
        } else {
            statusLabel?.stringValue = "● Checking..."
            statusLabel?.textColor = .secondaryLabelColor
            checkServer()
        }
    }

    @objc func goBack() { if webView.canGoBack { webView.goBack() } }
    @objc func goForward() { if webView.canGoForward { webView.goForward() } }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        switch message.name {
        case "retry": refreshPage()
        case "navBack": goBack()
        case "navForward": goForward()
        case "startServers":
            statusLabel?.stringValue = "● Starting..."
            statusLabel?.textColor = NSColor.systemOrange
            autoStartServer()
            checkServer()
        default: break
        }
    }

    func toolbar(_ toolbar: NSToolbar, itemForItemIdentifier itemIdentifier: NSToolbarItem.Identifier, willBeInsertedIntoToolbar flag: Bool) -> NSToolbarItem? {
        switch itemIdentifier.rawValue {
        case "logoItem":
            let item = NSToolbarItem(itemIdentifier: itemIdentifier)
            item.label = "Logo"
            
            let container = NSView(frame: NSRect(x: 0, y: 0, width: 90, height: 22))
            
            let dot = NSView(frame: NSRect(x: 0, y: 6, width: 8, height: 8))
            dot.wantsLayer = true
            dot.layer?.backgroundColor = NSColor(red: 1.0, green: 0.84, blue: 0.0, alpha: 1.0).cgColor
            dot.layer?.cornerRadius = 4
            
            let label = NSTextField(labelWithString: "J.E.N.N.Y.")
            label.frame = NSRect(x: 14, y: 0, width: 76, height: 20)
            label.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .bold)
            label.textColor = NSColor.white
            label.isBezeled = false
            label.drawsBackground = false
            label.isEditable = false
            label.isSelectable = false
            
            container.addSubview(dot)
            container.addSubview(label)
            item.view = container
            return item
        case "refreshItem":
            let item = NSToolbarItem(itemIdentifier: itemIdentifier)
            item.label = "Refresh"
            item.toolTip = "Refresh"
            let btn = NSButton(image: NSImage(systemSymbolName: "arrow.clockwise", accessibilityDescription: "Refresh")!, target: self, action: #selector(refreshPage))
            btn.bezelStyle = .inline
            item.view = btn
            return item
        case "backItem":
            let item = NSToolbarItem(itemIdentifier: itemIdentifier)
            item.label = "Back"
            let btn = NSButton(image: NSImage(systemSymbolName: "chevron.left", accessibilityDescription: "Back")!, target: self, action: #selector(goBack))
            btn.bezelStyle = .inline
            item.view = btn
            return item
        case "forwardItem":
            let item = NSToolbarItem(itemIdentifier: itemIdentifier)
            item.label = "Forward"
            let btn = NSButton(image: NSImage(systemSymbolName: "chevron.right", accessibilityDescription: "Forward")!, target: self, action: #selector(goForward))
            btn.bezelStyle = .inline
            item.view = btn
            return item
        case "statusItem":
            let item = NSToolbarItem(itemIdentifier: itemIdentifier)
            item.label = "Status"
            item.view = statusLabel
            return item
        default:
            return nil
        }
    }

    func toolbarAllowedItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        return allToolbarItems
    }

    func toolbarDefaultItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        return allToolbarItems
    }

    var allToolbarItems: [NSToolbarItem.Identifier] {
        return [
            NSToolbarItem.Identifier("logoItem"),
            NSToolbarItem.Identifier.flexibleSpace,
            NSToolbarItem.Identifier("backItem"),
            NSToolbarItem.Identifier("forwardItem"),
            NSToolbarItem.Identifier("refreshItem"),
            NSToolbarItem.Identifier.space,
            NSToolbarItem.Identifier("statusItem"),
        ]
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        healthTimer?.invalidate()
        return .terminateNow
    }
}

let desktopApp = NSApplication.shared
let desktopDelegate = DesktopAppDelegate()
desktopApp.delegate = desktopDelegate
desktopApp.run()
