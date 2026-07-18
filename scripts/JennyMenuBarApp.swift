import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    var statusItem: NSStatusItem!
    var popover: NSPopover!
    var webView: WKWebView!

    func applicationDidFinishLaunching(_ aNotification: Notification) {
        // Create status bar item in macOS menu bar
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        if let button = statusItem.button {
            button.title = "🌌 Jenny"
            button.action = #selector(menuItemClicked(_:))
            button.target = self
        }
        
        // Create macOS Native Popover Window (Mini Jenny UI)
        popover = NSPopover()
        popover.contentSize = NSSize(width: 380, height: 520)
        popover.behavior = .transient
        popover.animates = true

        let viewController = NSViewController()
        let config = WKWebViewConfiguration()
        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 380, height: 520), configuration: config)
        webView.navigationDelegate = self

        if let url = URL(string: "http://localhost:3000/mini.html") {
            webView.load(URLRequest(url: url))
        }

        viewController.view = webView
        popover.contentViewController = viewController

        constructMenu()
        print("[Jenny AI] macOS Menu Bar Popover Window initialized.")
    }

    func constructMenu() {
        let menu = NSMenu()
        
        let popoverItem = NSMenuItem(title: "🌌 Open Mini Jenny HUD", action: #selector(togglePopover(_:)), keyEquivalent: "s")
        popoverItem.target = self
        menu.addItem(popoverItem)

        let toggleItem = NSMenuItem(title: "🎙️ Speak to Jenny", action: #selector(toggleMic), keyEquivalent: "m")
        toggleItem.target = self
        menu.addItem(toggleItem)
        
        menu.addItem(NSMenuItem.separator())
        
        let openAppItem = NSMenuItem(title: "🖥️ Open Jenny Desktop App", action: #selector(openDesktopApp), keyEquivalent: "o")
        openAppItem.target = self
        menu.addItem(openAppItem)
        
        menu.addItem(NSMenuItem.separator())
        
        let quitItem = NSMenuItem(title: "❌ Quit Jenny", action: #selector(quitApp), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)
        
        statusItem.menu = menu
    }

    @objc func togglePopover(_ sender: AnyObject?) {
        if let button = statusItem.button {
            if popover.isShown {
                popover.performClose(sender)
            } else {
                if let url = URL(string: "http://localhost:3000/mini.html") {
                    webView.load(URLRequest(url: url))
                }
                popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
                popover.contentViewController?.view.window?.makeKey()
            }
        }
    }

    @objc func toggleMic() {
        guard let url = URL(string: "http://localhost:3000/api/toggle-mic") else { return }
        let task = URLSession.shared.dataTask(with: url)
        task.resume()
        togglePopover(nil)
    }

    @objc func openDesktopApp() {
        let appPath = Bundle.main.bundlePath + "/../JennyDesktop.app"
        let desktopAppUrl = URL(fileURLWithPath: appPath).standardized
        if FileManager.default.fileExists(atPath: desktopAppUrl.path) {
            NSWorkspace.shared.open(desktopAppUrl)
        } else if let url = URL(string: "http://localhost:3000") {
            NSWorkspace.shared.open(url)
        }
    }

    @objc func quitApp() {
        NSApplication.shared.terminate(nil)
    }

    @objc func menuItemClicked(_ sender: Any?) {
        togglePopover(sender as AnyObject?)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
