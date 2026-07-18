import Cocoa

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!

    func applicationDidFinishLaunching(_ aNotification: Notification) {
        // Create status bar item in macOS menu bar
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        if let button = statusItem.button {
            button.title = "🌌 Siri / Jenny"
            button.action = #selector(menuItemClicked(_:))
            button.target = self
        }
        
        constructMenu()
        print("[Jenny AI] macOS Menu Bar Siri Status Item initialized.")
    }

    func constructMenu() {
        let menu = NSMenu()
        
        let toggleItem = NSMenuItem(title: "🎙️ Speak to Siri / Jenny", action: #selector(toggleMic), keyEquivalent: "m")
        toggleItem.target = self
        menu.addItem(toggleItem)
        
        menu.addItem(NSMenuItem.separator())
        
        let openItem = NSMenuItem(title: "🌐 Open Siri Interface", action: #selector(openWebUI), keyEquivalent: "o")
        openItem.target = self
        menu.addItem(openItem)
        
        menu.addItem(NSMenuItem.separator())
        
        let quitItem = NSMenuItem(title: "❌ Quit Menu Bar App", action: #selector(quitApp), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)
        
        statusItem.menu = menu
    }

    @objc func toggleMic() {
        print("[Jenny AI] Menu bar mic toggle clicked.")
        guard let url = URL(string: "http://localhost:3000/api/toggle-mic") else { return }
        let task = URLSession.shared.dataTask(with: url) { data, response, error in
            if let error = error {
                print("[Jenny AI] Error toggling mic: \(error)")
            } else {
                print("[Jenny AI] Mic toggle signal sent successfully.")
            }
        }
        task.resume()
    }

    @objc func openWebUI() {
        if let url = URL(string: "http://localhost:3000") {
            NSWorkspace.shared.open(url)
        }
    }

    @objc func quitApp() {
        NSApplication.shared.terminate(nil)
    }

    @objc func menuItemClicked(_ sender: Any?) {
        toggleMic()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
