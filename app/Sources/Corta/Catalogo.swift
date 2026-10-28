import CryptoKit
import Foundation

/// Efectos de la comunidad (repo corta-app/corta-catalogo). Solo se descarga desde un dominio fijo, sin seguir redirecciones, con
/// tamaño máximo; el índice lo valida bin/efectos.py (el mismo formato que el catálogo) y cada efecto se compara con su huella
/// SHA-256 del índice validado antes de que Python lo vuelva a validar y lo guarde en ~/Corta/.corta/efectos/.
@MainActor
enum Catalogo {
    static let host = "raw.githubusercontent.com"
    static let base = "https://raw.githubusercontent.com/corta-app/corta-catalogo/main/"
    static let maxIndice = 512 * 1024
    static let maxEfecto = 64 * 1024
    /// Lo último que validó bin/efectos.py: de aquí salen la ruta y la huella de cada descarga (nunca de lo que manda la interfaz).
    private static var indice: [[String: Any]] = []

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
        let u = FileManager.default.temporaryDirectory.appendingPathComponent("corta-efecto-\(UUID().uuidString).json")
        try? datos.write(to: u, options: .atomic)
        return u
    }

    /// El índice del catálogo, validado por bin/efectos.py: {ok, efectos} o {ok: false, error}.
    static func listar(_ fin: @escaping @MainActor ([String: Any]) -> Void) {
        pedir("efectos/index.json", maximo: maxIndice) { datos in
            guard let datos else { return fin(["ok": false, "error": Idioma.t("No pude conectarme. Revisa tu conexión.")]) }
            let archivo = temporal(datos)
            Procesador.correrJSON("efectos.py", ["indice", archivo.path]) { r in
                try? FileManager.default.removeItem(at: archivo)
                indice = r["efectos"] as? [[String: Any]] ?? []
                fin(r["ok"] as? Bool == true ? ["ok": true, "efectos": indice] : ["ok": false, "error": Idioma.t("No pude leer el catálogo.")])
            }
        }
    }

    /// Descarga un efecto del índice validado, revisa tamaño y huella, y bin/efectos.py lo valida y lo guarda.
    static func descargar(_ id: String, _ fin: @escaping @MainActor ([String: Any]) -> Void) {
        let error = { (texto: String) in fin(["ok": false, "id": id, "error": Idioma.t(texto)]) }
        guard let e = indice.first(where: { $0["id"] as? String == id }),
              let ruta = e["archivo"] as? String, ruta.range(of: "^efectos/[a-z]+/[a-z0-9-]{2,40}\\.json$", options: .regularExpression) != nil,
              let huella = e["sha256"] as? String, let bytes = (e["bytes"] as? NSNumber)?.intValue, bytes <= maxEfecto else {
            return error("Ese efecto no es válido.")
        }
        pedir(ruta, maximo: maxEfecto) { datos in
            guard let datos else { return error("No pude conectarme. Revisa tu conexión.") }
            let calculada = SHA256.hash(data: datos).map { String(format: "%02x", $0) }.joined()
            guard datos.count == bytes, calculada == huella else { return error("El efecto llegó dañado. Intenta de nuevo.") }
            let archivo = temporal(datos)
            Procesador.conEntrada("efectos.py", "entrada", ["accion": "instalar", "archivo": archivo.path, "id": id, "sha256": huella]) { r in
                try? FileManager.default.removeItem(at: archivo)
                var x = r
                if r["ok"] as? Bool != true { x["id"] = id; x["error"] = Idioma.t(r["error"] as? String ?? "Ese efecto no es válido.") }
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
