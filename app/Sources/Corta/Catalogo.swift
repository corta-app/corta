import CryptoKit
import Foundation

/// El catálogo de la comunidad (repo corta-app/corta-catalogo): efectos y plantillas. Solo se descarga desde un dominio fijo, sin
/// seguir redirecciones, con tamaño máximo; el índice lo valida bin/efectos.py o bin/plantillas.py (el mismo formato que el
/// catálogo) y cada archivo se compara con su huella SHA-256 del índice validado antes de que Python lo vuelva a validar y lo
/// guarde en ~/Corta/.corta/efectos/ o ~/Corta/.corta/plantillas/.
@MainActor
enum Catalogo {
    /// Lo que hay en el catálogo: cada tipo tiene su carpeta, su índice, su script que valida y sus textos de error.
    enum Tipo: String {
        case efectos, plantillas
        var script: String { self == .efectos ? "efectos.py" : "plantillas.py" }
        /// `efectos/<categoria>/<id>.json` o `plantillas/<categoria>/<id>.json`.
        var patron: String { "^\(rawValue)/[a-z]+/[a-z0-9-]{2,40}\\.json$" }
        var noValido: String { self == .efectos ? "Ese efecto no es válido." : "Esa plantilla no es válida." }
        var danado: String { self == .efectos ? "El efecto llegó dañado. Intenta de nuevo." : "La plantilla llegó dañada. Intenta de nuevo." }
    }

    static let host = "raw.githubusercontent.com"
    static let base = "https://raw.githubusercontent.com/corta-app/corta-catalogo/main/"
    static let maxIndice = 512 * 1024
    static let maxArchivo = 64 * 1024
    /// Lo último que validó Python por tipo: de aquí salen la ruta y la huella de cada descarga (nunca de lo que manda la interfaz).
    private static var indices: [Tipo: [[String: Any]]] = [:]

    /// Pide `ruta` (relativa a `base`) y devuelve los datos solo si es una respuesta 200 del mismo dominio y no pasa del máximo.
    private static func pedir(_ ruta: String, maximo: Int, _ fin: @escaping @MainActor (Data?) -> Void) {
        guard let u = URL(string: base + ruta), u.scheme == "https", u.host == host else { fin(nil); return }
        var pedido = URLRequest(url: u, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        pedido.setValue("Corta/\(Actualizaciones.version)", forHTTPHeaderField: "User-Agent")
        let dominio = host
        let sesion = URLSession(configuration: .ephemeral, delegate: SinRedirecciones(), delegateQueue: nil)
        sesion.dataTask(with: pedido) { datos, respuesta, _ in
            let r = respuesta as? HTTPURLResponse
            let ok = r?.statusCode == 200 && r?.url?.host == dominio && (datos?.count ?? Int.max) <= maximo
            let d = ok ? datos : nil
            sesion.finishTasksAndInvalidate()
            Task { @MainActor in fin(d) }
        }.resume()
    }

    static func temporal(_ datos: Data) -> URL {
        let u = FileManager.default.temporaryDirectory.appendingPathComponent("corta-catalogo-\(UUID().uuidString).json")
        try? datos.write(to: u, options: .atomic)
        return u
    }

    /// El índice de un tipo, validado por Python: {ok, efectos | plantillas} o {ok: false, error}.
    static func listar(tipo: Tipo = .efectos, _ fin: @escaping @MainActor ([String: Any]) -> Void) {
        pedir("\(tipo.rawValue)/index.json", maximo: maxIndice) { datos in
            guard let datos else { return fin(["ok": false, "error": Idioma.t("No pude conectarme. Revisa tu conexión.")]) }
            let archivo = temporal(datos)
            Procesador.correrJSON(tipo.script, ["indice", archivo.path]) { r in
                try? FileManager.default.removeItem(at: archivo)
                let lista = r[tipo.rawValue] as? [[String: Any]] ?? []
                indices[tipo] = lista
                fin(r["ok"] as? Bool == true ? ["ok": true, tipo.rawValue: lista] : ["ok": false, "error": Idioma.t("No pude leer el catálogo.")])
            }
        }
    }

    /// Descarga un archivo del índice validado, revisa tamaño y huella, y Python lo valida y lo guarda.
    static func descargar(_ id: String, tipo: Tipo = .efectos, _ fin: @escaping @MainActor ([String: Any]) -> Void) {
        let error = { (texto: String) in fin(["ok": false, "id": id, "error": Idioma.t(texto)]) }
        guard let e = (indices[tipo] ?? []).first(where: { $0["id"] as? String == id }),
              let ruta = e["archivo"] as? String, ruta.range(of: tipo.patron, options: .regularExpression) != nil,
              let huella = e["sha256"] as? String, let bytes = (e["bytes"] as? NSNumber)?.intValue, bytes <= maxArchivo else {
            return error(tipo.noValido)
        }
        pedir(ruta, maximo: maxArchivo) { datos in
            guard let datos else { return error("No pude conectarme. Revisa tu conexión.") }
            let calculada = SHA256.hash(data: datos).map { String(format: "%02x", $0) }.joined()
            guard datos.count == bytes, calculada == huella else { return error(tipo.danado) }
            let archivo = temporal(datos)
            Procesador.conEntrada(tipo.script, "entrada", ["accion": "instalar", "archivo": archivo.path, "id": id, "sha256": huella]) { r in
                try? FileManager.default.removeItem(at: archivo)
                var x = r
                if r["ok"] as? Bool != true { x["id"] = id; x["error"] = Idioma.t(r["error"] as? String ?? tipo.noValido) }
                fin(x)
            }
        }
    }
}

/// Nunca sigue una redirección: una respuesta 3xx queda como está (y no es 200, así que se descarta).
final class SinRedirecciones: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest) async -> URLRequest? {
        nil
    }
}
