import AppKit
import UniformTypeIdentifiers
import WebKit

/// `corta://video/<carpeta>/<archivo>`: el video y la música de un proyecto para la vista previa, con rangos (Range) para poder
/// adelantar. La interfaz se carga con acceso de lectura solo a ui/; esto es lo único que puede leer fuera de ahí, y solo:
///   · el video del proyecto (`fuente.archivo` de su proyecto.json) o un archivo de su carpeta `musica/`,
///   · de una carpeta directa de ~/Corta con proyecto.json, y
///   · sin enlaces simbólicos que lleven fuera de ~/Corta.
/// Todo lo demás (otra ruta, «..», ~/Corta/.corta, otro esquema) no se sirve.
@MainActor
final class Medios: NSObject, WKURLSchemeHandler {
    static let esquema = "corta"
    /// Como máximo esto por respuesta: el reproductor pide lo que sigue con otro rango.
    static let trozo: Int64 = 4 << 20

    static func archivo(de url: URL) -> URL? {
        let prefijo = "\(esquema)://video/"
        let texto = url.absoluteString
        guard texto.hasPrefix(prefijo), !texto.contains("?"), !texto.contains("#"),
              let ruta = String(texto.dropFirst(prefijo.count)).removingPercentEncoding,
              ruta.hasPrefix("/"), !ruta.contains("\u{0}") else { return nil }
        let real = URL(fileURLWithPath: ruta).standardizedFileURL.resolvingSymlinksInPath()
        let base = Rutas.baseReal
        guard real.path.hasPrefix(base) else { return nil }
        let partes = real.path.dropFirst(base.count).split(separator: "/", omittingEmptySubsequences: false).map(String.init)
        guard partes.count == 2 || (partes.count == 3 && partes[1] == "musica"),
              let carpeta = partes.first, !carpeta.isEmpty, !carpeta.hasPrefix("."), partes.allSatisfy({ !$0.isEmpty }) else { return nil }
        let p = Archivos.leerJSON(URL(fileURLWithPath: base + carpeta).appendingPathComponent("proyecto.json"))
        guard let fuente = p["fuente"] as? [String: Any] else { return nil }
        if partes.count == 2, partes[1] != (fuente["archivo"] as? String) { return nil }
        var esDirectorio: ObjCBool = false
        guard FileManager.default.fileExists(atPath: real.path, isDirectory: &esDirectorio), !esDirectorio.boolValue else { return nil }
        return real
    }

    func webView(_ webView: WKWebView, start tarea: WKURLSchemeTask) {
        // Todo pasa aquí mismo (leer 4 MB de un disco local es rápido): así nunca se le responde a una tarea ya detenida.
        guard let url = tarea.request.url, let archivo = Medios.archivo(de: url),
              let total = (try? FileManager.default.attributesOfItem(atPath: archivo.path))?[.size] as? Int64,
              let h = try? FileHandle(forReadingFrom: archivo) else {
            tarea.didFailWithError(NSError(domain: NSURLErrorDomain, code: NSURLErrorFileDoesNotExist))
            return
        }
        defer { try? h.close() }
        let tipo = UTType(filenameExtension: archivo.pathExtension.lowercased())?.preferredMIMEType ?? "application/octet-stream"
        var desde: Int64 = 0, hasta: Int64 = total - 1, conRango = false
        if let r = tarea.request.value(forHTTPHeaderField: "Range"), let m = r.firstMatch(of: #/bytes=(\d*)-(\d*)/#) {
            conRango = true
            if m.1.isEmpty {
                desde = max(0, total - (Int64(m.2) ?? 0))  // «bytes=-N»: los últimos N
            } else {
                desde = Int64(m.1) ?? 0
                if let b = Int64(m.2) { hasta = min(b, total - 1) }
            }
        }
        guard total > 0, desde <= hasta, desde < total else {
            let vacia = HTTPURLResponse(url: url, statusCode: total == 0 ? 200 : 416, httpVersion: "HTTP/1.1",
                                        headerFields: ["Content-Type": tipo, "Content-Length": "0", "Content-Range": "bytes */\(total)"])!
            tarea.didReceive(vacia)
            tarea.didFinish()
            return
        }
        hasta = min(hasta, desde + Medios.trozo - 1)
        let datos: Data
        do {
            try h.seek(toOffset: UInt64(desde))
            datos = try h.read(upToCount: Int(hasta - desde + 1)) ?? Data()
        } catch {
            tarea.didFailWithError(error)
            return
        }
        let parcial = conRango || datos.count < total
        var cabeceras = ["Content-Type": tipo, "Content-Length": "\(datos.count)", "Accept-Ranges": "bytes", "Cache-Control": "no-store"]
        if parcial { cabeceras["Content-Range"] = "bytes \(desde)-\(desde + Int64(datos.count) - 1)/\(total)" }
        tarea.didReceive(HTTPURLResponse(url: url, statusCode: parcial ? 206 : 200, httpVersion: "HTTP/1.1", headerFields: cabeceras)!)
        tarea.didReceive(datos)
        tarea.didFinish()
    }

    func webView(_ webView: WKWebView, stop tarea: WKURLSchemeTask) {}
}
