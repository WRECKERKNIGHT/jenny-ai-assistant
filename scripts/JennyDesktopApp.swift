import Cocoa
import WebKit

let SERVER_URL = "http://localhost:3000"
let HEALTH_CHECK_TIMEOUT: TimeInterval = 2.0

func desktopLoadingHTML(status: String = "Connecting to JENNY server...") -> String {
    return """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
        background: #000; color: #fff;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Mono', monospace;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        height: 100vh; overflow: hidden;
    }
    .loader {
        width: 80px; height: 80px; border-radius: 50%;
        border: 2px solid rgba(0,242,254,0.15); border-top-color: #00f2fe;
        animation: spin 1s linear infinite; margin-bottom: 24px; position: relative;
    }
    .loader::after {
        content: ''; position: absolute; inset: 8px; border-radius: 50%;
        border: 2px solid rgba(255,0,127,0.15); border-bottom-color: #ff007f;
        animation: spin 1.5s linear infinite reverse;
    }
    .loader::before {
        content: ''; position: absolute; inset: 18px; border-radius: 50%;
        border: 1.5px solid rgba(121,40,202,0.15); border-left-color: #7928ca;
        animation: spin 2s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .title {
        font-size: 28px; font-weight: 700; letter-spacing: 8px;
        background: linear-gradient(90deg, #00f2fe, #7928ca, #ff007f);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 12px;
    }
    .subtitle { font-size: 12px; color: rgba(255,255,255,0.4); letter-spacing: 2px; margin-bottom: 6px; }
    .status { font-size: 11px; color: rgba(255,255,255,0.3); letter-spacing: 1px; }
    .retry-btn {
        margin-top: 30px; padding: 10px 28px; background: rgba(0,242,254,0.08);
        border: 1px solid rgba(0,242,254,0.25); border-radius: 10px; color: #00f2fe;
        font-family: inherit; font-size: 11px; letter-spacing: 1.5px; cursor: pointer;
    }
    .retry-btn:hover { background: rgba(0,242,254,0.15); border-color: #00f2fe; }
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

        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        config.userContentController.add(self, name: "retry")
        config.userContentController.add(self, name: "navBack")
        config.userContentController.add(self, name: "navForward")

        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.navigationDelegate = self
        webView.setValue(false, forKey: "drawsBackground")
        webView.autoresizingMask = [.width, .height]
        webView.loadHTMLString(desktopLoadingHTML(), baseURL: nil)

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
        statusLabel?.stringValue = online ? "● Online" : "● Auto-Starting Server..."
        statusLabel?.textColor = online ? NSColor.systemGreen : NSColor.systemOrange
        if online {
            loadMainUI()
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

    func loadMainUI() {
        guard let url = URL(string: SERVER_URL) else { return }
        let current = webView.url?.absoluteString ?? ""
        if !current.contains("localhost:3000") || current.contains("mini.html") || !serverOnline {
            webView.load(URLRequest(url: url))
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
        default: break
        }
    }

    func toolbar(_ toolbar: NSToolbar, itemForItemIdentifier itemIdentifier: NSToolbarItem.Identifier, willBeInsertedIntoToolbar flag: Bool) -> NSToolbarItem? {
        switch itemIdentifier.rawValue {
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
            NSToolbarItem.Identifier("refreshItem"),
            NSToolbarItem.Identifier("backItem"),
            NSToolbarItem.Identifier("forwardItem"),
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
