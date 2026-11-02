import AppKit
import PiezaHost

// MARK: - Rutas (las mismas de bin/proyecto.py)

/// La carpeta de datos (~/Corta/.corta), la config, el idioma, los scripts y la fila los pone la pieza «host-mac» (`Host`,
/// `Config`, `Idioma`, `Procesador`, `Fila`). Aquí queda lo de Corta: ~/Corta con sus proyectos y los programas de la app.
@MainActor
enum Rutas {
    /// Videos y proyectos de la persona: fuera de la app, así actualizar no borra nada. `Host.datos` es ~/Corta/.corta.
    static var base: URL { Host.datos.deletingLastPathComponent() }
    static var modelos: URL { Host.datos.appendingPathComponent("modelos") }
    /// ffmpeg, ffprobe y corta-transcribir: junto al ejecutable de la app (Contents/MacOS), verificados por huella al empaquetar.
    static var programas: URL { Bundle.main.executableURL!.deletingLastPathComponent() }

    /// ~/Corta sin enlaces simbólicos, terminada en «/», para comparar rutas.
    static var baseReal: String { base.resolvingSymlinksInPath().path + "/" }

    /// La carpeta de un proyecto que manda la interfaz: tiene que ser una carpeta directa de ~/Corta con su proyecto.json.
    /// (bin/proyecto.py `carpeta_valida` lo revisa otra vez.) Devuelve la ruta real o nil.
    static func proyecto(_ valor: Any?) -> String? {
        guard let s = valor as? String, s.hasPrefix("/"), !s.contains("\u{0}") else { return nil }
        let real = URL(fileURLWithPath: s).standardizedFileURL.resolvingSymlinksInPath()
        guard real.deletingLastPathComponent().path + "/" == baseReal, !real.lastPathComponent.hasPrefix("."),
              FileManager.default.fileExists(atPath: real.appendingPathComponent("proyecto.json").path) else { return nil }
        return real.path
    }

    /// Un archivo dentro de ~/Corta (para «Mostrar en la carpeta»), o nil.
    static func dentro(_ valor: Any?) -> URL? {
        guard let s = valor as? String, s.hasPrefix("/"), !s.contains("\u{0}") else { return nil }
        let real = URL(fileURLWithPath: s).standardizedFileURL.resolvingSymlinksInPath()
        guard real.path.hasPrefix(baseReal), FileManager.default.fileExists(atPath: real.path) else { return nil }
        return real
    }
}

// MARK: - Modelos de transcripción (whisper.cpp), descargados y verificados por huella (los mismos de Graba y Minuta)

struct ModeloWhisper {
    let id: String, nombre: String, archivo: String, bytes: Int64, sha256: String, detalle: String
}

@MainActor
enum Modelos {
    /// Los nombres de archivo son los que usa bin/importar.py (ARCHIVOS_MODELO). Nombre y detalle se traducen en la interfaz.
    static let lista: [ModeloWhisper] = [
        .init(id: "turbo", nombre: "Preciso", archivo: "ggml-large-v3-turbo-q5_0.bin", bytes: 574_041_195,
              sha256: "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2", detalle: "Mejor para cualquier idioma. 574 MB."),
        .init(id: "small", nombre: "Rápido", archivo: "ggml-small-q5_1.bin", bytes: 190_085_487,
              sha256: "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb", detalle: "Más liviano, un poco menos preciso. 190 MB."),
    ]

    static func existe(_ m: ModeloWhisper) -> Bool {
        let a = (try? FileManager.default.attributesOfItem(atPath: Rutas.modelos.appendingPathComponent(m.archivo).path))?[.size] as? Int64
        return a == m.bytes
    }

    static var hayAlguno: Bool { lista.contains(where: existe) }

    static var recomendado: String { ProcessInfo.processInfo.physicalMemory >= 8 << 30 ? "turbo" : "small" }

    static var paraJS: [String: Any] {
        ["recomendado": recomendado,
         "lista": lista.map { ["id": $0.id, "nombre": $0.nombre, "mb": Int($0.bytes / 1_000_000), "detalle": $0.detalle, "listo": existe($0)] }]
    }

    private static var descarga: Descarga?
    private static var ultimoPct = -1

    static func descargar(_ id: String, progreso: @escaping @MainActor (Double) -> Void, fin: @escaping @MainActor (Bool, String?) -> Void) {
        guard let m = lista.first(where: { $0.id == id }) else { fin(false, Idioma.t("No pude descargar.")); return }
        if existe(m) { fin(true, nil); return }
        guard descarga == nil else { fin(false, Idioma.t("Ya hay una descarga en curso.")); return }
        try? FileManager.default.createDirectory(at: Rutas.modelos, withIntermediateDirectories: true)
        let url = URL(string: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/\(m.archivo)")!
        ultimoPct = -1
        let d = Descarga(desde: url, sha256: m.sha256, destino: Rutas.modelos.appendingPathComponent(m.archivo),
                         progreso: { bytes in
                             // La interfaz se repinta con cada aviso: solo cuando cambia el porcentaje.
                             let pct = Int(Double(bytes) / Double(m.bytes) * 100)
                             guard pct != Modelos.ultimoPct else { return }
                             Modelos.ultimoPct = pct
                             progreso(min(1, Double(bytes) / Double(m.bytes)))
                         },
                         fin: { ok, error in descarga = nil; fin(ok, error) })
        descarga = d
        d.empezar()
    }
}

/// Descarga a un archivo temporal; solo lo deja en su lugar si la huella SHA-256 coincide.
final class Descarga: NSObject, URLSessionDownloadDelegate, @unchecked Sendable {
    let desde: URL, sha256: String, destino: URL
    let progreso: @MainActor (Int64) -> Void, fin: @MainActor (Bool, String?) -> Void

    init(desde: URL, sha256: String, destino: URL, progreso: @escaping @MainActor (Int64) -> Void, fin: @escaping @MainActor (Bool, String?) -> Void) {
        self.desde = desde; self.sha256 = sha256; self.destino = destino; self.progreso = progreso; self.fin = fin
    }

    func empezar() {
        URLSession(configuration: .default, delegate: self, delegateQueue: nil).downloadTask(with: desde).resume()
    }

    func urlSession(_ s: URLSession, downloadTask: URLSessionDownloadTask, didWriteData _: Int64, totalBytesWritten t: Int64, totalBytesExpectedToWrite _: Int64) {
        Task { @MainActor in self.progreso(t) }
    }

    func urlSession(_ s: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo ubicacion: URL) {
        let temporal = destino.appendingPathExtension("descarga")
        try? FileManager.default.removeItem(at: temporal)
        guard (try? FileManager.default.moveItem(at: ubicacion, to: temporal)) != nil else {
            Task { @MainActor in self.fin(false, Idioma.t("No pude guardar la descarga.")) }; return
        }
        let p = Process(), salida = Pipe()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/shasum")
        p.arguments = ["-a", "256", temporal.path]
        p.standardOutput = salida
        try? p.run(); p.waitUntilExit()
        let huella = String(data: salida.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?.split(separator: " ").first.map(String.init) ?? ""
        guard huella == sha256 else {
            try? FileManager.default.removeItem(at: temporal)
            Task { @MainActor in self.fin(false, Idioma.t("La descarga llegó dañada. Intenta de nuevo.")) }; return
        }
        try? FileManager.default.removeItem(at: destino)
        let ok = (try? FileManager.default.moveItem(at: temporal, to: destino)) != nil
        Task { @MainActor in self.fin(ok, ok ? nil : Idioma.t("No pude guardar la descarga.")) }
        s.finishTasksAndInvalidate()
    }

    func urlSession(_ s: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let error else { return }
        Task { @MainActor in self.fin(false, error.localizedDescription) }
        s.finishTasksAndInvalidate()
    }
}
