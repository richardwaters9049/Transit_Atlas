import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

enum HarnessError: Error, CustomStringConvertible {
    case message(String)
    var description: String {
        switch self {
        case .message(let value): return value
        }
    }
}

func require(_ condition: @autoclosure () -> Bool, _ message: String) throws {
    if !condition() { throw HarnessError.message(message) }
}

func attribute(_ element: AXUIElement, _ name: String) -> Any? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success else {
        return nil
    }
    return value
}

func children(_ element: AXUIElement) -> [AXUIElement] {
    attribute(element, kAXChildrenAttribute) as? [AXUIElement] ?? []
}

func findElement(
    _ element: AXUIElement,
    role wantedRole: String,
    title wantedTitle: String
) -> AXUIElement? {
    let role = attribute(element, kAXRoleAttribute) as? String ?? ""
    let title = attribute(element, kAXTitleAttribute) as? String ?? ""
    if role == wantedRole && title == wantedTitle { return element }
    for child in children(element) {
        if let match = findElement(child, role: wantedRole, title: wantedTitle) {
            return match
        }
    }
    return nil
}

func pointAndSize(_ element: AXUIElement) throws -> (CGPoint, CGSize) {
    guard
        let positionAttribute = attribute(element, kAXPositionAttribute),
        let sizeAttribute = attribute(element, kAXSizeAttribute)
    else {
        throw HarnessError.message("Could not read the plot's Accessibility frame.")
    }
    let rawPosition = positionAttribute as! AXValue
    let rawSize = sizeAttribute as! AXValue
    var point = CGPoint.zero
    var size = CGSize.zero
    guard AXValueGetValue(rawPosition, .cgPoint, &point),
          AXValueGetValue(rawSize, .cgSize, &size) else {
        throw HarnessError.message("The plot's Accessibility frame had an unexpected type.")
    }
    return (point, size)
}

func appElements() throws -> (AXUIElement, AXUIElement, CGPoint, CGSize) {
    guard let app = NSRunningApplication.runningApplications(
        withBundleIdentifier: "com.richardwaters.transitatlas"
    ).first else {
        throw HarnessError.message("Transit Atlas is not running.")
    }
    let root = AXUIElementCreateApplication(app.processIdentifier)
    guard let window = findElement(root, role: "AXWindow", title: "Transit Atlas") else {
        throw HarnessError.message("Transit Atlas main window is not available to Accessibility.")
    }
    guard let plot = findElement(
        window,
        role: "AXGroup",
        title: "Interactive three-dimensional point cloud"
    ) else {
        throw HarnessError.message("Could not locate the Three.js plot through Accessibility.")
    }
    let (position, size) = try pointAndSize(plot)
    return (root, window, position, size)
}

func postMouse(_ type: CGEventType, at point: CGPoint) throws {
    guard let event = CGEvent(
        mouseEventSource: nil,
        mouseType: type,
        mouseCursorPosition: point,
        mouseButton: .left
    ) else {
        throw HarnessError.message("Could not create a macOS mouse event.")
    }
    event.post(tap: .cghidEventTap)
}

func movePointerAway(from window: AXUIElement) throws {
    let (origin, size) = try pointAndSize(window)
    let point = CGPoint(x: origin.x + size.width - 16, y: origin.y + size.height - 16)
    try postMouse(.mouseMoved, at: point)
}

func screenshot(_ output: URL, plotPosition: CGPoint, plotSize: CGSize) throws {
    let raw = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("transit-atlas-screen-\(UUID().uuidString).png")
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
    process.arguments = ["-x", raw.path]
    try process.run()
    process.waitUntilExit()
    try require(process.terminationStatus == 0, "macOS screen capture failed.")

    let data = try Data(contentsOf: raw)
    guard let bitmap = NSBitmapImageRep(data: data), let fullImage = bitmap.cgImage else {
        throw HarnessError.message("Could not read the macOS screen capture.")
    }
    let scale = CGFloat(fullImage.width) / (NSScreen.main?.frame.width ?? 1512)
    let rect = CGRect(
        x: plotPosition.x * scale,
        y: plotPosition.y * scale,
        width: plotSize.width * scale,
        height: plotSize.height * scale
    ).integral
    guard let crop = fullImage.cropping(to: rect) else {
        throw HarnessError.message("Could not crop the plot from the macOS screen capture.")
    }
    let outputBitmap = NSBitmapImageRep(cgImage: crop)
    guard let png = outputBitmap.representation(using: .png, properties: [:]) else {
        throw HarnessError.message("Could not encode the plot screenshot.")
    }
    try png.write(to: output, options: .atomic)
    try? FileManager.default.removeItem(at: raw)
}

func capture(_ output: URL) throws {
    let (_, window, plotPosition, plotSize) = try appElements()
    try movePointerAway(from: window)
    Thread.sleep(forTimeInterval: 1)
    try screenshot(output, plotPosition: plotPosition, plotSize: plotSize)
    print("Captured plot: \(output.path)")
}

func rotate(_ output: URL) throws {
    let (_, window, plotPosition, plotSize) = try appElements()
    let start = CGPoint(
        x: plotPosition.x + plotSize.width * 0.40,
        y: plotPosition.y + plotSize.height * 0.52
    )
    let finish = CGPoint(
        x: plotPosition.x + plotSize.width * 0.72,
        y: plotPosition.y + plotSize.height * 0.24
    )
    try postMouse(.leftMouseDown, at: start)
    for step in 1...16 {
        let progress = CGFloat(step) / 16
        let point = CGPoint(
            x: start.x + (finish.x - start.x) * progress,
            y: start.y + (finish.y - start.y) * progress
        )
        try postMouse(.leftMouseDragged, at: point)
        usleep(15_000)
    }
    try postMouse(.leftMouseUp, at: finish)
    try movePointerAway(from: window)
    Thread.sleep(forTimeInterval: 1.5)
    try screenshot(output, plotPosition: plotPosition, plotSize: plotSize)
    print("Rotated plot captured: \(output.path)")
}

func meanDifference(_ lhs: URL, _ rhs: URL) throws -> Double {
    guard
        let a = NSBitmapImageRep(data: try Data(contentsOf: lhs)),
        let b = NSBitmapImageRep(data: try Data(contentsOf: rhs)),
        a.pixelsWide == b.pixelsWide,
        a.pixelsHigh == b.pixelsHigh
    else {
        throw HarnessError.message("Camera screenshots are missing or have different dimensions.")
    }

    var total = 0.0
    var samples = 0.0
    for y in stride(from: 0, to: a.pixelsHigh, by: 8) {
        for x in stride(from: 0, to: a.pixelsWide, by: 8) {
            guard
                let left = a.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB),
                let right = b.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB)
            else { continue }
            total += abs(Double(left.redComponent - right.redComponent)) * 255
            total += abs(Double(left.greenComponent - right.greenComponent)) * 255
            total += abs(Double(left.blueComponent - right.blueComponent)) * 255
            samples += 3
        }
    }
    return total / samples
}

func compare(_ baseline: URL, _ rotated: URL, _ restored: URL) throws {
    let changed = try meanDifference(baseline, rotated)
    let replayed = try meanDifference(baseline, restored)
    print(String(format: "Camera image difference — rotated: %.3f, restored: %.3f", changed, replayed))
    try require(changed > 1.5, "The automation drag did not produce a measurable camera change.")
    try require(replayed < 0.5, "Reopened study did not restore the saved 3D camera orientation.")
    print("PASS: saved camera orientation was restored by native study replay.")
}

do {
    guard CommandLine.arguments.count >= 3 else {
        throw HarnessError.message(
            "Usage: macos-study-camera.swift capture|rotate <output.png> | compare <baseline.png> <rotated.png> <restored.png>"
        )
    }
    let mode = CommandLine.arguments[1]
    switch mode {
    case "capture":
        try capture(URL(fileURLWithPath: CommandLine.arguments[2]))
    case "rotate":
        try rotate(URL(fileURLWithPath: CommandLine.arguments[2]))
    case "compare":
        guard CommandLine.arguments.count == 5 else {
            throw HarnessError.message("compare requires baseline, rotated and restored image paths.")
        }
        try compare(
            URL(fileURLWithPath: CommandLine.arguments[2]),
            URL(fileURLWithPath: CommandLine.arguments[3]),
            URL(fileURLWithPath: CommandLine.arguments[4])
        )
    default:
        throw HarnessError.message("Unknown camera test mode: \(mode)")
    }
} catch {
    fputs("FAIL: \(error)\n", stderr)
    exit(1)
}
