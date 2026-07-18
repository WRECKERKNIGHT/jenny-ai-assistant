import Cocoa
import WebKit

class DesktopAppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var webView: WKWebView!

    func applicationDidFinishLaunching(_ aNotification: Notification) {
        let rect = NSRect(x: 100, y: 100, width: 1280, height: 850)
        window = NSWindow(contentRect: rect,
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered,
                          defer: false)
        window.title = "Jenny AI Neural Assistant"
        window.titlebarAppearsTransparent = true
        window.center()

        let config = WKWebViewConfiguration()
        webView = WKWebView(frame: rect, configuration: config)
        webView.navigationDelegate = self

        if let url = URL(string: "http://localhost:3000") {
            webView.load(URLRequest(url: url))
        }

        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        print("[Jenny AI] Standalone Desktop App launched.")
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

let desktopApp = NSApplication.shared
let desktopDelegate = DesktopAppDelegate()
desktopApp.delegate = desktopDelegate
desktopApp.run()
