package fungsi;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.security.InvalidAlgorithmParameterException;
import java.security.InvalidKeyException;
import java.security.KeyManagementException;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.Collections;
import java.util.Iterator;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.crypto.BadPaddingException;
import javax.crypto.IllegalBlockSizeException;
import javax.crypto.NoSuchPaddingException;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import org.apache.http.conn.scheme.Scheme;
import org.apache.http.conn.ssl.SSLSocketFactory;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.BufferingClientHttpRequestFactory;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.http.client.HttpComponentsClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

public class ApiSatuSehat {
    private String key, clientid, urlauth, token;
    private long millis;
    private SSLContext sslContext;
    private SSLSocketFactory sslFactory;
    private Scheme scheme;
    private HttpComponentsClientHttpRequestFactory factory;
    private ApiBPJSAesKeySpec mykey;
    private HttpHeaders header;
    private JsonNode root;
    private HttpEntity requestEntity;
    private ObjectMapper mapper = new ObjectMapper();

    private static String cachedToken = "";
    private static long cachedTokenExpiredAtMillis = 0;

    private static final long TOKEN_EXPIRY_SAFETY_MILLIS = 60000;
    private static final ObjectMapper JSON_MAPPER = new ObjectMapper();
    private static final Pattern NO_RAWAT_PATTERN = Pattern.compile("\\d{4}/\\d{2}/\\d{2}/\\d{6}");
    private static final ThreadLocal<ObjectNode> KHANZA_SOURCE_ROW = new ThreadLocal<ObjectNode>();

    private static class StaticClientHttpResponse implements ClientHttpResponse {
        private final HttpStatus status;
        private final String body;
        private final HttpHeaders headers;

        private StaticClientHttpResponse(HttpStatus status, String body, HttpHeaders headers) {
            this.status = status;
            this.body = body == null ? "" : body;
            this.headers = headers == null ? new HttpHeaders() : headers;
        }

        @Override
        public HttpStatus getStatusCode() throws IOException {
            return status;
        }

        public int getRawStatusCode() throws IOException {
            return status.value();
        }

        @Override
        public String getStatusText() throws IOException {
            return status.getReasonPhrase();
        }

        @Override
        public void close() {
        }

        @Override
        public InputStream getBody() throws IOException {
            return new ByteArrayInputStream(body.getBytes(StandardCharsets.UTF_8));
        }

        @Override
        public HttpHeaders getHeaders() {
            return headers;
        }
    }

    private static final ClientHttpRequestInterceptor ERPNEXT_CANONICAL_FORWARDER =
            new ClientHttpRequestInterceptor() {
                @Override
                public ClientHttpResponse intercept(
                        HttpRequest request,
                        byte[] body,
                        ClientHttpRequestExecution execution
                ) throws IOException {
                    if (!isErpNextForwardingEnabled() || !isClinicalPayloadSubmit(request, body)) {
                        return execution.execute(request, body);
                    }

                    return forwardCanonicalToErpNext(request, body);
                }
            };

    public ApiSatuSehat() {
        try {
            key = koneksiDB.SECRETKEYSATUSEHAT();
            clientid = koneksiDB.CLIENTIDSATUSEHAT();
            urlauth = koneksiDB.URLAUTHSATUSEHAT();
        } catch (Exception ex) {
            System.out.println("Notifikasi : " + ex);
        }
    }

    public synchronized String TokenSatuSehat() {
        long now = System.currentTimeMillis();

        if (cachedToken != null
                && !cachedToken.trim().equals("")
                && cachedTokenExpiredAtMillis > now + TOKEN_EXPIRY_SAFETY_MILLIS) {
            return cachedToken;
        }

        try {
            header = new HttpHeaders();
            header.setContentType(MediaType.APPLICATION_FORM_URLENCODED);
            requestEntity = new HttpEntity(
                    "client_id=" + URLEncoder.encode(clientid, "UTF-8")
                    + "&client_secret=" + URLEncoder.encode(key, "UTF-8"),
                    header
            );
            root = mapper.readTree(
                    createRestTemplate(false)
                            .exchange(
                                    urlauth + "/accesstoken?grant_type=client_credentials",
                                    HttpMethod.POST,
                                    requestEntity,
                                    String.class
                            )
                            .getBody()
            );
            token = root.path("access_token").asText();

            if (token != null && !token.trim().equals("")) {
                long expiresInSeconds = root.path("expires_in").asLong(3000);
                cachedToken = token;
                cachedTokenExpiredAtMillis = now + (expiresInSeconds * 1000);
                System.out.println(
                        "Notifikasi : Token SatuSehat berhasil dibuat"
                        + " | panjang=" + token.length()
                        + " | expires_in=" + expiresInSeconds + " detik"
                );
            } else {
                System.out.println("Notifikasi : Token SatuSehat kosong dari response OAuth : " + root);
            }
        } catch (Exception ex) {
            System.out.println("Notifikasi : Gagal mengambil Token SatuSehat : " + ex);
        }

        if (cachedToken != null && !cachedToken.trim().equals("")) {
            return cachedToken;
        }

        return "";
    }

    public long GetUTCdatetimeAsString() {
        millis = System.currentTimeMillis();
        return millis / 1000;
    }

    public String Decrypt(String data, String utc)
            throws NoSuchPaddingException, NoSuchAlgorithmException,
            InvalidAlgorithmParameterException, InvalidKeyException,
            BadPaddingException, IllegalBlockSizeException {
        System.out.println(data);
        mykey = ApiBPJSEnc.generateKey(clientid + key + utc);
        data = ApiBPJSEnc.decrypt(data, mykey.getKey(), mykey.getIv());
        data = ApiBPJSLZString.decompressFromEncodedURIComponent(data);
        System.out.println(data);
        return data;
    }

    public RestTemplate getRest() throws NoSuchAlgorithmException, KeyManagementException {
        return createRestTemplate(true);
    }

    public String AuthorizationKlinis() {
        if (isErpNextForwardingEnabled()) {
            return "";
        }
        return "Bearer " + TokenSatuSehat();
    }

    public String toKhanzaFlatJson(ResultSet row, String sourceJson, String method, String requestUrl) {
        try {
            JsonNode source = parseJsonQuietly(sourceJson);
            URI uri = requestUrl == null || requestUrl.trim().equals("") ? null : URI.create(requestUrl);
            String recordType = firstNonEmpty(
                    extractResourceTypeFromPath(uri),
                    extractResourceType(source),
                    "unknown"
            );
            String endpointPath = buildEndpointPath(uri, method, null, recordType);

            ObjectNode flat = JSON_MAPPER.createObjectNode();
            flat.put("resource_type", recordType);
            flat.put("method", safe(method));
            flat.put("endpoint_path", endpointPath);
            flat.put("request_url", safe(requestUrl));

            appendResultSetFields(flat, row);
            appendFlatRelations(flat, row, recordType);

            String externalId = firstNonEmpty(
                    valueFromRow(row, "external_id"),
                    buildFlatExternalId(recordType, method, row)
            );
            flat.put("external_id", externalId);

            appendFlatFinancial(flat, buildFinancialFromRow(recordType, row));
            return flat.toString();
        } catch (Exception ex) {
            System.out.println("[SATUSEHAT-ERP] Gagal membuat JSON flat Khanza : " + ex);
            return sourceJson;
        }
    }

    public void setKhanzaSourceRow(ResultSet source) {
        if (source == null) {
            KHANZA_SOURCE_ROW.remove();
            return;
        }

        try {
            ObjectNode row = JSON_MAPPER.createObjectNode();
            ResultSetMetaData metaData = source.getMetaData();
            for (int i = 1; i <= metaData.getColumnCount(); i++) {
                String label = metaData.getColumnLabel(i);
                if (label == null || label.trim().equals("")) {
                    label = metaData.getColumnName(i);
                }
                label = label == null ? "column_" + i : label.trim();
                Object value = source.getObject(i);
                if (value == null) {
                    row.putNull(label);
                } else {
                    row.put(label, String.valueOf(value));
                }
            }
            KHANZA_SOURCE_ROW.set(row);
        } catch (Exception ex) {
            KHANZA_SOURCE_ROW.remove();
            System.out.println("[SATUSEHAT-ERP] Gagal snapshot row Khanza : " + ex);
        }
    }

    private RestTemplate createRestTemplate(boolean withErpNextForwarder)
            throws NoSuchAlgorithmException, KeyManagementException {
        sslContext = SSLContext.getInstance("TLSv1.2");
        TrustManager[] trustManagers = {
            new X509TrustManager() {
                @Override
                public X509Certificate[] getAcceptedIssuers() {
                    return null;
                }

                @Override
                public void checkServerTrusted(X509Certificate[] arg0, String arg1)
                        throws CertificateException {
                }

                @Override
                public void checkClientTrusted(X509Certificate[] arg0, String arg1)
                        throws CertificateException {
                }
            }
        };
        sslContext.init(null, trustManagers, new SecureRandom());
        sslFactory = new SSLSocketFactory(sslContext, SSLSocketFactory.ALLOW_ALL_HOSTNAME_VERIFIER);
        scheme = new Scheme("https", 443, sslFactory);
        factory = new HttpComponentsClientHttpRequestFactory();
        factory.getHttpClient().getConnectionManager().getSchemeRegistry().register(scheme);

        RestTemplate restTemplate = new RestTemplate(
                new BufferingClientHttpRequestFactory(factory)
        );

        if (withErpNextForwarder) {
            restTemplate.setInterceptors(new ClientHttpRequestInterceptor[]{
                ERPNEXT_CANONICAL_FORWARDER
            });
        }

        return restTemplate;
    }

    private static boolean isErpNextForwardingEnabled() {
        String endpoint = koneksiDB.ERPNEXTSATUSEHATURL();
        if (endpoint == null || endpoint.trim().equals("")) {
            return false;
        }

        String enabled = koneksiDB.ERPNEXTSATUSEHATENABLE();
        if (enabled == null || enabled.trim().equals("")) {
            return true;
        }

        enabled = enabled.trim().toLowerCase();
        return !enabled.equals("false")
                && !enabled.equals("0")
                && !enabled.equals("no")
                && !enabled.equals("tidak");
    }

    private static boolean isClinicalPayloadSubmit(HttpRequest request, byte[] body) {
        try {
            if (request == null || request.getURI() == null || isTokenUrl(request.getURI())) {
                return false;
            }

            String method = request.getMethod() == null ? "" : request.getMethod().name();
            if (!"POST".equalsIgnoreCase(method) && !"PUT".equalsIgnoreCase(method)) {
                return false;
            }

            String requestBody = body == null ? "" : new String(body, StandardCharsets.UTF_8);
            JsonNode fhir = parseJsonQuietly(requestBody);
            String resourceType = extractResourceType(fhir);

            if (resourceType == null || resourceType.trim().equals("")) {
                resourceType = extractResourceTypeFromPath(request.getURI());
            }

            return resourceType != null && !resourceType.trim().equals("");
        } catch (Exception e) {
            System.out.println("[SATUSEHAT-ERP] Gagal cek request klinis : " + e);
            return false;
        }
    }

    private static ClientHttpResponse forwardCanonicalToErpNext(
            HttpRequest request,
            byte[] requestBodyBytes
    ) throws IOException {
        String endpoint = koneksiDB.ERPNEXTSATUSEHATURL();
        String apiKey = koneksiDB.ERPNEXTSATUSEHATAPIKEY();

        if (endpoint == null || endpoint.trim().equals("")) {
            throw new IOException("ERPNEXTSATUSEHATURL kosong. Payload klinis tidak bisa diteruskan ke ERPNext.");
        }

        String requestBody = requestBodyBytes == null
                ? ""
                : new String(requestBodyBytes, StandardCharsets.UTF_8);
        JsonNode fhir = JSON_MAPPER.readTree(requestBody);
        String resourceType = extractResourceType(fhir);

        if (resourceType == null || resourceType.trim().equals("")) {
            resourceType = extractResourceTypeFromPath(request.getURI());
        }
        if (resourceType == null || resourceType.trim().equals("")) {
            throw new IOException("Jenis record klinis tidak ditemukan di request Khanza.");
        }

        if (isKhanzaFlatJson(fhir)) {
            ResponseEntity<String> response = sendToErpNext(endpoint, apiKey, fhir.toString());
            String externalId = firstNonEmpty(textAt(fhir, "external_id"), buildExternalId("POST", "/" + resourceType, fhir, resourceType));
            System.out.println(
                    "[SATUSEHAT-ERP] Flat JSON Khanza diteruskan ke ERPNext"
                    + " | resource_type=" + resourceType
                    + " | status=" + response.getStatusCode().value()
                    + " | external_id=" + externalId
            );
            return new StaticClientHttpResponse(
                    response.getStatusCode(),
                    buildKhanzaAckBody(fhir, resourceType, externalId),
                    buildAckHeaders()
            );
        }

        String method = request.getMethod() == null ? "POST" : request.getMethod().name();
        String endpointPath = buildEndpointPath(request.getURI(), method, fhir, resourceType);
        String externalId = buildExternalId(method, endpointPath, fhir, resourceType);

        ObjectNode payload = JSON_MAPPER.createObjectNode();
        payload.put("external_id", externalId);
        payload.put("resource_type", resourceType);
        payload.put("method", method);
        payload.put("endpoint_path", endpointPath);
        payload.put("request_url", request.getURI().toString());
        appendFlattenedSourceFields(payload, fhir);
        appendFlatFinancial(payload, buildFinancial(resourceType, fhir));

        ResponseEntity<String> response = sendToErpNext(endpoint, apiKey, payload.toString());
        String ackBody = buildKhanzaAckBody(fhir, resourceType, externalId);

        System.out.println(
                "[SATUSEHAT-ERP] Canonical JSON diteruskan ke ERPNext"
                + " | resourceType=" + resourceType
                + " | method=" + method
                + " | status=" + response.getStatusCode().value()
                + " | external_id=" + externalId
        );

        return new StaticClientHttpResponse(
                response.getStatusCode(),
                ackBody,
                buildAckHeaders()
        );
    }

    private static ResponseEntity<String> sendToErpNext(
            String endpoint,
            String apiKey,
            String payload
    ) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(Collections.singletonList(MediaType.APPLICATION_JSON));

        if (apiKey != null && !apiKey.trim().equals("")) {
            headers.add("Authorization", "token " + apiKey.trim());
        }

        return createForwardingRestTemplate().exchange(
                endpoint,
                HttpMethod.POST,
                new HttpEntity<String>(payload, headers),
                String.class
        );
    }

    private static boolean isKhanzaFlatJson(JsonNode node) {
        if (node == null || !node.isObject()) {
            return false;
        }
        return textAt(node, "resourceType").equals("")
                && !textAt(node, "resource_type").equals("");
    }

    private static RestTemplate createForwardingRestTemplate() {
        return new RestTemplate();
    }

    private static ObjectNode buildFinancial(String resourceType, JsonNode fhir) {
        ObjectNode financial = JSON_MAPPER.createObjectNode();
        ObjectNode keys = financial.putObject("keys");
        ArrayNode direct = financial.putArray("direct");
        ArrayNode referencePrices = financial.putArray("reference_prices");

        financial.put("currency", "IDR");
        financial.put("resource_type", safe(resourceType));
        addIdentifierKeys(financial, keys, fhir);

        String noRawat = extractNoRawat(fhir);
        String noResep = extractNoResep(fhir);
        String kodeBrng = extractKodeBrng(fhir);
        String noOrder = extractNoOrder(fhir);
        String detailKey = extractDetailKey(fhir);
        String eventDateTime = extractEventDateTime(fhir);
        String eventDate = datePart(eventDateTime);
        String eventTime = timePart(eventDateTime);

        putIfNotEmpty(keys, "no_rawat", noRawat);
        putIfNotEmpty(keys, "no_resep", noResep);
        putIfNotEmpty(keys, "kode_brng", kodeBrng);
        putIfNotEmpty(keys, "noorder", noOrder);
        putIfNotEmpty(keys, "detail_key", detailKey);
        putIfNotEmpty(keys, "event_date", eventDate);
        putIfNotEmpty(keys, "event_time", eventTime);

        try {
            if ("Encounter".equalsIgnoreCase(resourceType)) {
                appendEncounterFinancial(financial, direct, noRawat, true);
            } else {
                appendEncounterFinancial(financial, null, noRawat, false);
                appendResourceFinancial(resourceType, fhir, direct, referencePrices, noRawat, noResep, kodeBrng, noOrder, detailKey, eventDate, eventTime);
            }
        } catch (Exception ex) {
            addFinancialWarning(financial, "Gagal membuat financial metadata: " + ex.getMessage());
        }

        financial.put("has_direct_financial", direct.size() > 0);
        financial.put("has_reference_prices", referencePrices.size() > 0);
        return financial;
    }

    private static ObjectNode buildFinancialFromRow(String resourceType, ResultSet row) {
        ObjectNode financial = JSON_MAPPER.createObjectNode();
        ObjectNode keys = financial.putObject("keys");
        ArrayNode direct = financial.putArray("direct");
        ArrayNode referencePrices = financial.putArray("reference_prices");

        financial.put("currency", "IDR");
        financial.put("resource_type", safe(resourceType));

        String noRawat = valueFromRow(row, "no_rawat");
        String noResep = valueFromRow(row, "no_resep");
        String kodeBrng = valueFromRow(row, "kode_brng");
        String noOrder = valueFromRow(row, "noorder");
        String detailKey = firstNonEmpty(
                valueFromRow(row, "id_template"),
                valueFromRow(row, "kd_jenis_prw"),
                valueFromRow(row, "kode"),
                valueFromRow(row, "kd_penyakit")
        );
        String eventDate = firstNonEmpty(
                valueFromRow(row, "tgl_perawatan"),
                valueFromRow(row, "tgl_periksa"),
                valueFromRow(row, "tgl_hasil"),
                valueFromRow(row, "tgl_registrasi"),
                valueFromRow(row, "tgl_permintaan"),
                valueFromRow(row, "tgl_penyerahan")
        );
        String eventTime = firstNonEmpty(
                valueFromRow(row, "jam_rawat"),
                valueFromRow(row, "jam"),
                valueFromRow(row, "jam_hasil"),
                valueFromRow(row, "jam_reg"),
                valueFromRow(row, "jam_permintaan"),
                valueFromRow(row, "jam_penyerahan")
        );

        putIfNotEmpty(keys, "no_rawat", noRawat);
        putIfNotEmpty(keys, "no_resep", noResep);
        putIfNotEmpty(keys, "kode_brng", kodeBrng);
        putIfNotEmpty(keys, "noorder", noOrder);
        putIfNotEmpty(keys, "detail_key", detailKey);
        putIfNotEmpty(keys, "event_date", eventDate);
        putIfNotEmpty(keys, "event_time", eventTime);

        try {
            if ("Encounter".equalsIgnoreCase(resourceType)) {
                appendEncounterFinancial(financial, direct, noRawat, true);
            } else {
                appendEncounterFinancial(financial, null, noRawat, false);
                appendResourceFinancialFromRow(resourceType, direct, referencePrices, noRawat, noResep, kodeBrng, noOrder, detailKey, eventDate, eventTime);
            }
        } catch (Exception ex) {
            addFinancialWarning(financial, "Gagal membuat financial metadata dari row: " + ex.getMessage());
        }

        financial.put("has_direct_financial", direct.size() > 0);
        financial.put("has_reference_prices", referencePrices.size() > 0);
        return financial;
    }

    private static void appendResourceFinancialFromRow(
            String resourceType,
            ArrayNode direct,
            ArrayNode referencePrices,
            String noRawat,
            String noResep,
            String kodeBrng,
            String noOrder,
            String detailKey,
            String eventDate,
            String eventTime
    ) {
        if ("Medication".equalsIgnoreCase(resourceType)) {
            appendMedicationReferencePrices(referencePrices, kodeBrng);
            appendMedicationUsageLines(direct, noRawat, kodeBrng, "", "");
            return;
        }

        if ("MedicationRequest".equalsIgnoreCase(resourceType)
                || "MedicationStatement".equalsIgnoreCase(resourceType)) {
            appendMedicationReferencePrices(referencePrices, kodeBrng);
            appendPrescriptionFinancial(direct, noResep, kodeBrng);
            appendMedicationUsageLines(direct, noRawat, kodeBrng, noResep, "");
            return;
        }

        if ("MedicationDispense".equalsIgnoreCase(resourceType)) {
            appendMedicationReferencePrices(referencePrices, kodeBrng);
            appendPrescriptionFinancial(direct, noResep, kodeBrng);
            appendMedicationUsageLines(direct, noRawat, kodeBrng, noResep, eventDate + " " + eventTime);
            return;
        }

        if ("Immunization".equalsIgnoreCase(resourceType)) {
            appendMedicationReferencePrices(referencePrices, kodeBrng);
            appendMedicationUsageLines(direct, noRawat, kodeBrng, "", eventDate + " " + eventTime);
            return;
        }

        if ("ServiceRequest".equalsIgnoreCase(resourceType)
                || "Specimen".equalsIgnoreCase(resourceType)
                || "Observation".equalsIgnoreCase(resourceType)
                || "DiagnosticReport".equalsIgnoreCase(resourceType)) {
            appendLaboratoryFinancial(direct, referencePrices, noOrder, detailKey);
            appendRadiologyFinancial(direct, referencePrices, noOrder, detailKey, firstNonEmpty(noOrder, detailKey));
        }
    }

    private static void appendResourceFinancial(
            String resourceType,
            JsonNode fhir,
            ArrayNode direct,
            ArrayNode referencePrices,
            String noRawat,
            String noResep,
            String kodeBrng,
            String noOrder,
            String detailKey,
            String eventDate,
            String eventTime
    ) {
        if ("Medication".equalsIgnoreCase(resourceType)) {
            appendMedicationReferencePrices(referencePrices, kodeBrng);
            appendMedicationUsageLines(direct, noRawat, kodeBrng, "", "");
            return;
        }

        if ("MedicationRequest".equalsIgnoreCase(resourceType)
                || "MedicationStatement".equalsIgnoreCase(resourceType)) {
            appendMedicationReferencePrices(referencePrices, kodeBrng);
            appendPrescriptionFinancial(direct, noResep, kodeBrng);
            appendMedicationUsageLines(direct, noRawat, kodeBrng, noResep, "");
            return;
        }

        if ("MedicationDispense".equalsIgnoreCase(resourceType)) {
            appendMedicationReferencePrices(referencePrices, kodeBrng);
            appendPrescriptionFinancial(direct, noResep, kodeBrng);
            appendMedicationUsageLines(direct, noRawat, kodeBrng, noResep, eventDate + " " + eventTime);
            return;
        }

        if ("Immunization".equalsIgnoreCase(resourceType)) {
            appendImmunizationFinancial(direct, referencePrices, fhir, noRawat, eventDate, eventTime);
            return;
        }

        if ("ServiceRequest".equalsIgnoreCase(resourceType)
                || "Specimen".equalsIgnoreCase(resourceType)
                || "Observation".equalsIgnoreCase(resourceType)
                || "DiagnosticReport".equalsIgnoreCase(resourceType)) {
            if (isLaboratoryResource(fhir, noOrder, detailKey)) {
                appendLaboratoryFinancial(direct, referencePrices, noOrder, detailKey);
            }
            if (isRadiologyResource(fhir, noOrder, detailKey)) {
                appendRadiologyFinancial(direct, referencePrices, noOrder, detailKey, firstIdentifierValue(fhir));
            }
        }
    }

    private static void appendEncounterFinancial(
            ObjectNode financial,
            ArrayNode direct,
            String noRawat,
            boolean includeLines
    ) {
        if (noRawat.equals("")) {
            return;
        }

        ArrayNode summary = financial.putArray("encounter_summary");
        appendRowsQuietly(
                financial,
                summary,
                "billing",
                "select billing.status,count(*) as line_count,sum(billing.biaya) as total_biaya,sum(billing.jumlah) as total_jumlah,"
                        + "sum(billing.tambahan) as total_tambahan,sum(billing.totalbiaya) as total_billing "
                        + "from billing where billing.no_rawat=? group by billing.status order by billing.status",
                noRawat
        );

        if (includeLines && direct != null) {
            appendRowsQuietly(
                    financial,
                    direct,
                    "billing",
                    "select billing.noindex,billing.no_rawat,billing.tgl_byr,billing.no,billing.nm_perawatan,"
                            + "billing.pemisah,billing.biaya,billing.jumlah,billing.tambahan,billing.totalbiaya,billing.status "
                            + "from billing where billing.no_rawat=? order by billing.noindex",
                    noRawat
            );

            appendRowsQuietly(
                    financial,
                    direct,
                    "nota_jalan",
                    "select nota_jalan.no_rawat,nota_jalan.no_nota,nota_jalan.tanggal,nota_jalan.jam "
                            + "from nota_jalan where nota_jalan.no_rawat=?",
                    noRawat
            );

            appendRowsQuietly(
                    financial,
                    direct,
                    "nota_inap",
                    "select nota_inap.no_rawat,nota_inap.no_nota,nota_inap.tanggal,nota_inap.jam,nota_inap.Uang_Muka "
                            + "from nota_inap where nota_inap.no_rawat=?",
                    noRawat
            );

            appendRowsQuietly(
                    financial,
                    direct,
                    "piutang_pasien",
                    "select piutang_pasien.no_rawat,piutang_pasien.tgl_piutang,piutang_pasien.no_rkm_medis,piutang_pasien.status,"
                            + "piutang_pasien.totalpiutang,piutang_pasien.uangmuka,piutang_pasien.sisapiutang,piutang_pasien.tgltempo "
                            + "from piutang_pasien where piutang_pasien.no_rawat=?",
                    noRawat
            );

            appendRowsQuietly(
                    financial,
                    direct,
                    "bayar_piutang",
                    "select bayar_piutang.no_rawat,bayar_piutang.tgl_bayar,bayar_piutang.no_rkm_medis,bayar_piutang.besar_cicilan,"
                            + "bayar_piutang.diskon_piutang,bayar_piutang.tidak_terbayar,bayar_piutang.catatan "
                            + "from bayar_piutang where bayar_piutang.no_rawat=?",
                    noRawat
            );

            appendRowsQuietly(
                    financial,
                    direct,
                    "kamar_inap",
                    "select kamar_inap.no_rawat,kamar_inap.kd_kamar,kamar_inap.trf_kamar,kamar_inap.tgl_masuk,kamar_inap.jam_masuk,"
                            + "kamar_inap.tgl_keluar,kamar_inap.jam_keluar,kamar_inap.lama,kamar_inap.ttl_biaya,kamar_inap.stts_pulang "
                            + "from kamar_inap where kamar_inap.no_rawat=?",
                    noRawat
            );
        }
    }

    private static void appendMedicationReferencePrices(ArrayNode referencePrices, String kodeBrng) {
        if (kodeBrng.equals("")) {
            return;
        }

        appendRowsQuietly(
                null,
                referencePrices,
                "databarang",
                "select databarang.kode_brng,databarang.nama_brng,databarang.dasar,databarang.h_beli,databarang.ralan,"
                        + "databarang.kelas1,databarang.kelas2,databarang.kelas3,databarang.utama,databarang.vip,databarang.vvip,"
                        + "databarang.beliluar,databarang.jualbebas,databarang.karyawan,databarang.status "
                        + "from databarang where databarang.kode_brng=?",
                kodeBrng
        );
    }

    private static void appendPrescriptionFinancial(ArrayNode direct, String noResep, String kodeBrng) {
        if (noResep.equals("") || kodeBrng.equals("")) {
            return;
        }

        appendRowsQuietly(
                null,
                direct,
                "resep_dokter",
                "select resep_obat.no_resep,resep_obat.no_rawat,resep_obat.tgl_peresepan,resep_obat.jam_peresepan,"
                        + "resep_dokter.kode_brng,databarang.nama_brng,resep_dokter.jml,resep_dokter.aturan_pakai,"
                        + "databarang.h_beli,databarang.ralan as harga_jual_referensi,(resep_dokter.jml*databarang.ralan) as estimasi_total "
                        + "from resep_obat inner join resep_dokter on resep_dokter.no_resep=resep_obat.no_resep "
                        + "left join databarang on databarang.kode_brng=resep_dokter.kode_brng "
                        + "where resep_obat.no_resep=? and resep_dokter.kode_brng=?",
                noResep,
                kodeBrng
        );
    }

    private static void appendMedicationUsageLines(
            ArrayNode direct,
            String noRawat,
            String kodeBrng,
            String noResep,
            String dateTime
    ) {
        if (kodeBrng.equals("")) {
            return;
        }

        String date = "";
        String time = "";
        if (dateTime != null && dateTime.trim().length() >= 11) {
            String[] parts = dateTime.trim().split(" ");
            if (parts.length > 0) {
                date = parts[0];
            }
            if (parts.length > 1) {
                time = normalizeTime(parts[1]);
            }
        }

        if (!noRawat.equals("") && !date.equals("") && !time.equals("")) {
            appendRowsQuietly(
                    null,
                    direct,
                    "detail_pemberian_obat",
                    medicationUsageSql()
                            + " where detail_pemberian_obat.no_rawat=? and detail_pemberian_obat.kode_brng=? "
                            + "and detail_pemberian_obat.tgl_perawatan=? and detail_pemberian_obat.jam=?",
                    noRawat,
                    kodeBrng,
                    date,
                    time
            );
            return;
        }

        if (!noResep.equals("")) {
            appendRowsQuietly(
                    null,
                    direct,
                    "detail_pemberian_obat",
                    medicationUsageSql()
                            + " inner join resep_obat on resep_obat.no_rawat=detail_pemberian_obat.no_rawat "
                            + "and resep_obat.tgl_perawatan=detail_pemberian_obat.tgl_perawatan "
                            + "and resep_obat.jam=detail_pemberian_obat.jam "
                            + "where resep_obat.no_resep=? and detail_pemberian_obat.kode_brng=?",
                    noResep,
                    kodeBrng
            );
            return;
        }

        if (!noRawat.equals("")) {
            appendRowsQuietly(
                    null,
                    direct,
                    "detail_pemberian_obat",
                    medicationUsageSql()
                            + " where detail_pemberian_obat.no_rawat=? and detail_pemberian_obat.kode_brng=?",
                    noRawat,
                    kodeBrng
            );
        }
    }

    private static String medicationUsageSql() {
        return "select detail_pemberian_obat.tgl_perawatan,detail_pemberian_obat.jam,detail_pemberian_obat.no_rawat,"
                + "detail_pemberian_obat.kode_brng,databarang.nama_brng,detail_pemberian_obat.h_beli,"
                + "detail_pemberian_obat.biaya_obat,detail_pemberian_obat.jml,detail_pemberian_obat.embalase,"
                + "detail_pemberian_obat.tuslah,detail_pemberian_obat.total,detail_pemberian_obat.status,"
                + "detail_pemberian_obat.kd_bangsal,detail_pemberian_obat.no_batch,detail_pemberian_obat.no_faktur "
                + "from detail_pemberian_obat left join databarang on databarang.kode_brng=detail_pemberian_obat.kode_brng ";
    }

    private static void appendImmunizationFinancial(
            ArrayNode direct,
            ArrayNode referencePrices,
            JsonNode fhir,
            String noRawat,
            String eventDate,
            String eventTime
    ) {
        String lotNumber = textAt(fhir, "lotNumber");
        String vaccineCode = firstCodingCode(fhir.path("vaccineCode"));
        String kodeBrng = lookupSingleValue(
                "select satu_sehat_mapping_vaksin.kode_brng from satu_sehat_mapping_vaksin "
                        + "where satu_sehat_mapping_vaksin.vaksin_code=? limit 1",
                vaccineCode
        );

        appendMedicationReferencePrices(referencePrices, kodeBrng);

        if (noRawat.equals("") || kodeBrng.equals("")) {
            return;
        }

        if (!eventDate.equals("") && !eventTime.equals("") && !lotNumber.equals("")) {
            appendRowsQuietly(
                    null,
                    direct,
                    "detail_pemberian_obat",
                    medicationUsageSql()
                            + " where detail_pemberian_obat.no_rawat=? and detail_pemberian_obat.kode_brng=? "
                            + "and detail_pemberian_obat.tgl_perawatan=? and detail_pemberian_obat.jam=? "
                            + "and detail_pemberian_obat.no_batch=?",
                    noRawat,
                    kodeBrng,
                    eventDate,
                    eventTime,
                    lotNumber
            );
        } else {
            appendMedicationUsageLines(direct, noRawat, kodeBrng, "", "");
        }
    }

    private static void appendLaboratoryFinancial(ArrayNode direct, ArrayNode referencePrices, String noOrder, String detailKey) {
        LabKey key = splitOrderAndDetail(noOrder, detailKey);
        if (key.noOrder.equals("") || key.detail.equals("")) {
            return;
        }

        appendRowsQuietly(
                null,
                referencePrices,
                "jns_perawatan_lab",
                "select jns_perawatan_lab.kd_jenis_prw,jns_perawatan_lab.nm_perawatan,jns_perawatan_lab.bagian_rs,"
                        + "jns_perawatan_lab.bhp,jns_perawatan_lab.tarif_perujuk,jns_perawatan_lab.tarif_tindakan_dokter,"
                        + "jns_perawatan_lab.tarif_tindakan_petugas,jns_perawatan_lab.kso,jns_perawatan_lab.menejemen,"
                        + "jns_perawatan_lab.total_byr,jns_perawatan_lab.kategori "
                        + "from permintaan_detail_permintaan_lab inner join jns_perawatan_lab "
                        + "on jns_perawatan_lab.kd_jenis_prw=permintaan_detail_permintaan_lab.kd_jenis_prw "
                        + "where permintaan_detail_permintaan_lab.noorder=? and permintaan_detail_permintaan_lab.id_template=? "
                        + "union all "
                        + "select jns_perawatan_lab.kd_jenis_prw,jns_perawatan_lab.nm_perawatan,jns_perawatan_lab.bagian_rs,"
                        + "jns_perawatan_lab.bhp,jns_perawatan_lab.tarif_perujuk,jns_perawatan_lab.tarif_tindakan_dokter,"
                        + "jns_perawatan_lab.tarif_tindakan_petugas,jns_perawatan_lab.kso,jns_perawatan_lab.menejemen,"
                        + "jns_perawatan_lab.total_byr,jns_perawatan_lab.kategori "
                        + "from permintaan_detail_permintaan_labmb inner join jns_perawatan_lab "
                        + "on jns_perawatan_lab.kd_jenis_prw=permintaan_detail_permintaan_labmb.kd_jenis_prw "
                        + "where permintaan_detail_permintaan_labmb.noorder=? and permintaan_detail_permintaan_labmb.id_template=?",
                key.noOrder,
                key.detail,
                key.noOrder,
                key.detail
        );

        appendRowsQuietly(
                null,
                direct,
                "periksa_lab",
                "select 'PK' as lab_source,permintaan_lab.noorder,permintaan_detail_permintaan_lab.id_template,"
                        + "permintaan_detail_permintaan_lab.kd_jenis_prw,periksa_lab.no_rawat,periksa_lab.tgl_periksa,periksa_lab.jam,"
                        + "periksa_lab.bagian_rs,periksa_lab.bhp,periksa_lab.tarif_perujuk,periksa_lab.tarif_tindakan_dokter,"
                        + "periksa_lab.tarif_tindakan_petugas,periksa_lab.kso,periksa_lab.menejemen,periksa_lab.biaya,"
                        + "detail_periksa_lab.biaya_item,detail_periksa_lab.bagian_rs as item_bagian_rs,detail_periksa_lab.bhp as item_bhp,"
                        + "detail_periksa_lab.bagian_perujuk,detail_periksa_lab.bagian_dokter,detail_periksa_lab.bagian_laborat,"
                        + "detail_periksa_lab.kso as item_kso,detail_periksa_lab.menejemen as item_menejemen "
                        + "from permintaan_lab inner join permintaan_detail_permintaan_lab on permintaan_detail_permintaan_lab.noorder=permintaan_lab.noorder "
                        + "left join periksa_lab on periksa_lab.no_rawat=permintaan_lab.no_rawat and periksa_lab.kd_jenis_prw=permintaan_detail_permintaan_lab.kd_jenis_prw "
                        + "and periksa_lab.tgl_periksa=permintaan_lab.tgl_hasil and periksa_lab.jam=permintaan_lab.jam_hasil "
                        + "left join detail_periksa_lab on detail_periksa_lab.no_rawat=periksa_lab.no_rawat and detail_periksa_lab.kd_jenis_prw=periksa_lab.kd_jenis_prw "
                        + "and detail_periksa_lab.tgl_periksa=periksa_lab.tgl_periksa and detail_periksa_lab.jam=periksa_lab.jam "
                        + "and detail_periksa_lab.id_template=permintaan_detail_permintaan_lab.id_template "
                        + "where permintaan_detail_permintaan_lab.noorder=? and permintaan_detail_permintaan_lab.id_template=? "
                        + "union all "
                        + "select 'MB' as lab_source,permintaan_labmb.noorder,permintaan_detail_permintaan_labmb.id_template,"
                        + "permintaan_detail_permintaan_labmb.kd_jenis_prw,periksa_lab.no_rawat,periksa_lab.tgl_periksa,periksa_lab.jam,"
                        + "periksa_lab.bagian_rs,periksa_lab.bhp,periksa_lab.tarif_perujuk,periksa_lab.tarif_tindakan_dokter,"
                        + "periksa_lab.tarif_tindakan_petugas,periksa_lab.kso,periksa_lab.menejemen,periksa_lab.biaya,"
                        + "detail_periksa_lab.biaya_item,detail_periksa_lab.bagian_rs as item_bagian_rs,detail_periksa_lab.bhp as item_bhp,"
                        + "detail_periksa_lab.bagian_perujuk,detail_periksa_lab.bagian_dokter,detail_periksa_lab.bagian_laborat,"
                        + "detail_periksa_lab.kso as item_kso,detail_periksa_lab.menejemen as item_menejemen "
                        + "from permintaan_labmb inner join permintaan_detail_permintaan_labmb on permintaan_detail_permintaan_labmb.noorder=permintaan_labmb.noorder "
                        + "left join periksa_lab on periksa_lab.no_rawat=permintaan_labmb.no_rawat and periksa_lab.kd_jenis_prw=permintaan_detail_permintaan_labmb.kd_jenis_prw "
                        + "and periksa_lab.tgl_periksa=permintaan_labmb.tgl_hasil and periksa_lab.jam=permintaan_labmb.jam_hasil "
                        + "left join detail_periksa_lab on detail_periksa_lab.no_rawat=periksa_lab.no_rawat and detail_periksa_lab.kd_jenis_prw=periksa_lab.kd_jenis_prw "
                        + "and detail_periksa_lab.tgl_periksa=periksa_lab.tgl_periksa and detail_periksa_lab.jam=periksa_lab.jam "
                        + "and detail_periksa_lab.id_template=permintaan_detail_permintaan_labmb.id_template "
                        + "where permintaan_detail_permintaan_labmb.noorder=? and permintaan_detail_permintaan_labmb.id_template=?",
                key.noOrder,
                key.detail,
                key.noOrder,
                key.detail
        );
    }

    private static void appendRadiologyFinancial(
            ArrayNode direct,
            ArrayNode referencePrices,
            String noOrder,
            String detailKey,
            String rawIdentifier
    ) {
        RadiologyKey key = splitRadiologyKey(noOrder, detailKey, rawIdentifier);
        if (key.lookupCompact.equals("") && key.lookupDotted.equals("") && (key.noOrder.equals("") || key.kdJenisPrw.equals(""))) {
            return;
        }

        appendRowsQuietly(
                null,
                referencePrices,
                "jns_perawatan_radiologi",
                "select jns_perawatan_radiologi.kd_jenis_prw,jns_perawatan_radiologi.nm_perawatan,jns_perawatan_radiologi.bagian_rs,"
                        + "jns_perawatan_radiologi.bhp,jns_perawatan_radiologi.tarif_perujuk,jns_perawatan_radiologi.tarif_tindakan_dokter,"
                        + "jns_perawatan_radiologi.tarif_tindakan_petugas,jns_perawatan_radiologi.kso,jns_perawatan_radiologi.menejemen,"
                        + "jns_perawatan_radiologi.total_byr,jns_perawatan_radiologi.kelas "
                        + "from permintaan_pemeriksaan_radiologi inner join jns_perawatan_radiologi "
                        + "on jns_perawatan_radiologi.kd_jenis_prw=permintaan_pemeriksaan_radiologi.kd_jenis_prw "
                        + "where (permintaan_pemeriksaan_radiologi.noorder=? and permintaan_pemeriksaan_radiologi.kd_jenis_prw=?) "
                        + "or concat(replace(permintaan_pemeriksaan_radiologi.noorder,'PR',''),permintaan_pemeriksaan_radiologi.kd_jenis_prw)=? "
                        + "or concat(permintaan_pemeriksaan_radiologi.noorder,'.',permintaan_pemeriksaan_radiologi.kd_jenis_prw)=?",
                key.noOrder,
                key.kdJenisPrw,
                key.lookupCompact,
                key.lookupDotted
        );

        appendRowsQuietly(
                null,
                direct,
                "periksa_radiologi",
                "select permintaan_radiologi.noorder,permintaan_pemeriksaan_radiologi.kd_jenis_prw,periksa_radiologi.no_rawat,"
                        + "periksa_radiologi.tgl_periksa,periksa_radiologi.jam,periksa_radiologi.bagian_rs,periksa_radiologi.bhp,"
                        + "periksa_radiologi.tarif_perujuk,periksa_radiologi.tarif_tindakan_dokter,periksa_radiologi.tarif_tindakan_petugas,"
                        + "periksa_radiologi.kso,periksa_radiologi.menejemen,periksa_radiologi.biaya,periksa_radiologi.status "
                        + "from permintaan_pemeriksaan_radiologi inner join permintaan_radiologi "
                        + "on permintaan_radiologi.noorder=permintaan_pemeriksaan_radiologi.noorder "
                        + "left join periksa_radiologi on periksa_radiologi.no_rawat=permintaan_radiologi.no_rawat "
                        + "and periksa_radiologi.kd_jenis_prw=permintaan_pemeriksaan_radiologi.kd_jenis_prw "
                        + "and periksa_radiologi.tgl_periksa=permintaan_radiologi.tgl_hasil "
                        + "and periksa_radiologi.jam=permintaan_radiologi.jam_hasil "
                        + "where (permintaan_pemeriksaan_radiologi.noorder=? and permintaan_pemeriksaan_radiologi.kd_jenis_prw=?) "
                        + "or concat(replace(permintaan_pemeriksaan_radiologi.noorder,'PR',''),permintaan_pemeriksaan_radiologi.kd_jenis_prw)=? "
                        + "or concat(permintaan_pemeriksaan_radiologi.noorder,'.',permintaan_pemeriksaan_radiologi.kd_jenis_prw)=?",
                key.noOrder,
                key.kdJenisPrw,
                key.lookupCompact,
                key.lookupDotted
        );
    }

    private static int appendRowsQuietly(
            ObjectNode financial,
            ArrayNode target,
            String sourceTable,
            String sql,
            Object... params
    ) {
        try {
            return appendRows(target, sourceTable, sql, params);
        } catch (Exception ex) {
            if (financial != null) {
                addFinancialWarning(financial, sourceTable + ": " + ex.getMessage());
            } else {
                System.out.println("[SATUSEHAT-ERP] Financial metadata dilewati untuk " + sourceTable + " : " + ex);
            }
            return 0;
        }
    }

    private static int appendRows(
            ArrayNode target,
            String sourceTable,
            String sql,
            Object... params
    ) throws Exception {
        if (target == null || sql == null || sql.trim().equals("")) {
            return 0;
        }

        Connection connection = null;
        PreparedStatement statement = null;
        ResultSet resultSet = null;
        int count = 0;

        try {
            connection = koneksiDB.condb();
            statement = connection.prepareStatement(sql);
            if (params != null) {
                for (int i = 0; i < params.length; i++) {
                    statement.setObject(i + 1, params[i]);
                }
            }
            resultSet = statement.executeQuery();
            ResultSetMetaData metaData = resultSet.getMetaData();
            int columns = metaData.getColumnCount();
            while (resultSet.next()) {
                ObjectNode row = JSON_MAPPER.createObjectNode();
                row.put("source_table", sourceTable);
                for (int i = 1; i <= columns; i++) {
                    putSqlValue(row, metaData.getColumnLabel(i), resultSet.getObject(i));
                }
                target.add(row);
                count++;
            }
        } finally {
            if (resultSet != null) {
                try {
                    resultSet.close();
                } catch (Exception ignored) {
                }
            }
            if (statement != null) {
                try {
                    statement.close();
                } catch (Exception ignored) {
                }
            }
        }

        return count;
    }

    private static void putSqlValue(ObjectNode row, String column, Object value) {
        String field = column == null ? "value" : column;
        if (value == null) {
            row.putNull(field);
        } else if (value instanceof Integer || value instanceof Long || value instanceof Short || value instanceof Byte) {
            row.put(field, ((Number) value).longValue());
        } else if (value instanceof Float || value instanceof Double) {
            row.put(field, ((Number) value).doubleValue());
        } else if (value instanceof java.math.BigDecimal) {
            row.put(field, (java.math.BigDecimal) value);
        } else if (value instanceof Boolean) {
            row.put(field, ((Boolean) value).booleanValue());
        } else {
            row.put(field, value.toString());
        }
    }

    private static void addFinancialWarning(ObjectNode financial, String warning) {
        if (financial == null || warning == null || warning.trim().equals("")) {
            return;
        }
        ArrayNode warnings;
        if (financial.has("warnings") && financial.path("warnings").isArray()) {
            warnings = (ArrayNode) financial.path("warnings");
        } else {
            warnings = financial.putArray("warnings");
        }
        warnings.add(warning);
    }

    private static void addIdentifierKeys(ObjectNode financial, ObjectNode keys, JsonNode fhir) {
        ArrayNode identifiers = financial.putArray("identifiers");
        JsonNode identifier = fhir == null ? null : fhir.path("identifier");
        if (identifier == null || !identifier.isArray()) {
            return;
        }

        for (int i = 0; i < identifier.size(); i++) {
            JsonNode item = identifier.get(i);
            ObjectNode row = identifiers.addObject();
            row.put("system", textAt(item, "system"));
            row.put("value", textAt(item, "value"));
        }
    }

    private static String extractNoRawat(JsonNode fhir) {
        String resourceType = extractResourceType(fhir);
        if ("Encounter".equalsIgnoreCase(resourceType)) {
            String value = firstIdentifierValue(fhir);
            if (isNoRawat(value)) {
                return value;
            }
        }

        String noRawat = noRawatFromText(collectIdentifierSource(fhir));
        if (!noRawat.equals("")) {
            return noRawat;
        }

        noRawat = noRawatFromText(extractBusinessReference(fhir));
        if (!noRawat.equals("")) {
            return noRawat;
        }

        String encounterReference = firstNonEmpty(
                referenceAt(fhir.path("encounter")),
                referenceAt(fhir.path("context"))
        );
        if (encounterReference.startsWith("Encounter/")) {
            String encounterId = encounterReference.substring("Encounter/".length());
            noRawat = lookupSingleValue(
                    "select satu_sehat_encounter.no_rawat from satu_sehat_encounter "
                            + "where satu_sehat_encounter.id_encounter=? limit 1",
                    encounterId
            );
            if (!noRawat.equals("")) {
                return noRawat;
            }
        }

        return noRawatFromText(fhir == null ? "" : fhir.toString());
    }

    private static String extractNoResep(JsonNode fhir) {
        String value = identifierValueBySystemContains(fhir, "/prescription/");
        if (!value.equals("")) {
            return value;
        }

        value = firstIdentifierValue(fhir);
        int split = value.indexOf("-");
        if (split > 0 && value.toLowerCase().startsWith("20")) {
            return value.substring(0, split);
        }
        return "";
    }

    private static String extractKodeBrng(JsonNode fhir) {
        String value = identifierValueBySystemContains(fhir, "/prescription-item/");
        if (!value.equals("")) {
            return value;
        }

        value = identifierValueBySystemContains(fhir, "/medication/");
        if (!value.equals("")) {
            return value;
        }

        value = firstIdentifierValue(fhir);
        int split = value.indexOf("-");
        if (split > 0 && split + 1 < value.length()) {
            String possible = value.substring(split + 1);
            if (possible.startsWith("B")) {
                return possible;
            }
        }
        return "";
    }

    private static String extractNoOrder(JsonNode fhir) {
        String value = firstIdentifierValue(fhir);
        if (value.indexOf(".") > 0) {
            return value.substring(0, value.indexOf("."));
        }
        if (value.startsWith("P") || value.startsWith("R")) {
            return value;
        }
        return "";
    }

    private static String extractDetailKey(JsonNode fhir) {
        String value = firstIdentifierValue(fhir);
        if (value.indexOf(".") > 0 && value.indexOf(".") + 1 < value.length()) {
            return value.substring(value.indexOf(".") + 1);
        }
        return value;
    }

    private static String extractEventDateTime(JsonNode fhir) {
        return firstNonEmpty(
                textAt(fhir, "whenHandedOver"),
                textAt(fhir, "whenPrepared"),
                textAt(fhir, "authoredOn"),
                textAt(fhir, "dateAsserted"),
                textAt(fhir, "occurrenceDateTime"),
                textAt(fhir, "effectiveDateTime"),
                textAt(fhir, "performedDateTime"),
                textAt(fhir, "issued"),
                textAt(fhir, "recordedDate")
        );
    }

    private static boolean isLaboratoryResource(JsonNode fhir, String noOrder, String detailKey) {
        String text = fhir == null ? "" : fhir.toString().toLowerCase();
        if (text.contains("imaging") || text.contains("radiologi") || text.contains("/acsn/")) {
            return false;
        }
        if (text.contains("laboratory") || text.contains("/lab") || text.contains("laborat")) {
            return true;
        }
        return (!noOrder.equals("") && !detailKey.equals("") && !detailKey.equals(noOrder));
    }

    private static boolean isRadiologyResource(JsonNode fhir, String noOrder, String detailKey) {
        String text = fhir == null ? "" : fhir.toString().toLowerCase();
        if (text.contains("imaging") || text.contains("radiologi") || text.contains("/acsn/")) {
            return true;
        }
        return detailKey != null && !detailKey.equals("") && !detailKey.equals(noOrder) && noOrder.toUpperCase().startsWith("R");
    }

    private static String identifierValueBySystemContains(JsonNode fhir, String marker) {
        JsonNode identifier = fhir == null ? null : fhir.path("identifier");
        if (identifier == null || !identifier.isArray()) {
            return "";
        }

        String lowerMarker = marker == null ? "" : marker.toLowerCase();
        for (int i = 0; i < identifier.size(); i++) {
            JsonNode item = identifier.get(i);
            String system = textAt(item, "system").toLowerCase();
            if (system.contains(lowerMarker)) {
                return textAt(item, "value");
            }
        }

        return "";
    }

    private static String lookupSingleValue(String sql, Object... params) {
        Connection connection = null;
        PreparedStatement statement = null;
        ResultSet resultSet = null;
        try {
            connection = koneksiDB.condb();
            statement = connection.prepareStatement(sql);
            if (params != null) {
                for (int i = 0; i < params.length; i++) {
                    statement.setObject(i + 1, params[i]);
                }
            }
            resultSet = statement.executeQuery();
            if (resultSet.next()) {
                Object value = resultSet.getObject(1);
                return value == null ? "" : value.toString().trim();
            }
        } catch (Exception ex) {
            System.out.println("[SATUSEHAT-ERP] Lookup financial metadata gagal : " + ex);
        } finally {
            if (resultSet != null) {
                try {
                    resultSet.close();
                } catch (Exception ignored) {
                }
            }
            if (statement != null) {
                try {
                    statement.close();
                } catch (Exception ignored) {
                }
            }
        }
        return "";
    }

    private static String noRawatFromText(String value) {
        if (value == null || value.equals("")) {
            return "";
        }
        Matcher matcher = NO_RAWAT_PATTERN.matcher(value);
        return matcher.find() ? matcher.group() : "";
    }

    private static boolean isNoRawat(String value) {
        return value != null && NO_RAWAT_PATTERN.matcher(value).matches();
    }

    private static String referenceAt(JsonNode node) {
        if (node == null || !node.isObject()) {
            return "";
        }
        return textAt(node, "reference");
    }

    private static String firstCodingCode(JsonNode codeable) {
        if (codeable == null) {
            return "";
        }
        JsonNode coding = codeable.path("coding");
        if (coding.isArray() && coding.size() > 0) {
            return textAt(coding.get(0), "code");
        }
        return "";
    }

    private static String datePart(String dateTime) {
        if (dateTime == null || dateTime.length() < 10) {
            return "";
        }
        return dateTime.substring(0, 10);
    }

    private static String timePart(String dateTime) {
        if (dateTime == null) {
            return "";
        }
        int t = dateTime.indexOf("T");
        if (t < 0 || t + 1 >= dateTime.length()) {
            return "";
        }
        String time = dateTime.substring(t + 1);
        int plus = time.indexOf("+");
        int z = time.indexOf("Z");
        int end = time.length();
        if (plus >= 0) {
            end = Math.min(end, plus);
        }
        if (z >= 0) {
            end = Math.min(end, z);
        }
        return normalizeTime(time.substring(0, end));
    }

    private static String normalizeTime(String time) {
        if (time == null) {
            return "";
        }
        time = time.trim();
        if (time.length() >= 8) {
            return time.substring(0, 8);
        }
        return time;
    }

    private static void putIfNotEmpty(ObjectNode node, String field, String value) {
        if (node != null && value != null && !value.trim().equals("")) {
            node.put(field, value.trim());
        }
    }

    private static LabKey splitOrderAndDetail(String noOrder, String detailKey) {
        if (noOrder == null) {
            noOrder = "";
        }
        if (detailKey == null) {
            detailKey = "";
        }
        if (noOrder.indexOf(".") > 0) {
            String[] parts = noOrder.split("\\.", 2);
            return new LabKey(parts[0], parts.length > 1 ? parts[1] : detailKey);
        }
        if (detailKey.indexOf(".") > 0) {
            String[] parts = detailKey.split("\\.", 2);
            return new LabKey(parts[0], parts.length > 1 ? parts[1] : "");
        }
        return new LabKey(noOrder, detailKey);
    }

    private static RadiologyKey splitRadiologyKey(String noOrder, String detailKey, String rawIdentifier) {
        String lookupCompact = rawIdentifier == null ? "" : rawIdentifier.trim();
        String lookupDotted = lookupCompact;
        if (lookupDotted.indexOf(".") < 0 && noOrder != null && detailKey != null && !noOrder.equals("") && !detailKey.equals("")) {
            lookupDotted = noOrder + "." + detailKey;
        }
        LabKey split = splitOrderAndDetail(noOrder, detailKey);
        return new RadiologyKey(split.noOrder, split.detail, lookupCompact, lookupDotted);
    }

    private static class LabKey {
        private final String noOrder;
        private final String detail;

        private LabKey(String noOrder, String detail) {
            this.noOrder = noOrder == null ? "" : noOrder.trim();
            this.detail = detail == null ? "" : detail.trim();
        }
    }

    private static class RadiologyKey {
        private final String noOrder;
        private final String kdJenisPrw;
        private final String lookupCompact;
        private final String lookupDotted;

        private RadiologyKey(String noOrder, String kdJenisPrw, String lookupCompact, String lookupDotted) {
            this.noOrder = noOrder == null ? "" : noOrder.trim();
            this.kdJenisPrw = kdJenisPrw == null ? "" : kdJenisPrw.trim();
            this.lookupCompact = lookupCompact == null ? "" : lookupCompact.trim();
            this.lookupDotted = lookupDotted == null ? "" : lookupDotted.trim();
        }
    }

    private static void appendResultSetFields(ObjectNode target, ResultSet row) throws Exception {
        if (target == null || row == null) {
            return;
        }

        ResultSetMetaData meta = row.getMetaData();
        if (meta == null) {
            return;
        }

        for (int i = 1; i <= meta.getColumnCount(); i++) {
            String key = normalizeFlatKey(firstNonEmpty(meta.getColumnLabel(i), meta.getColumnName(i)));
            if (key.equals("")) {
                key = "column_" + i;
            }
            if (target.has(key)) {
                key = uniqueFlatKey(target, "row_" + key);
            }

            String value = row.getString(i);
            if (value == null) {
                target.putNull(key);
            } else {
                target.put(key, value);
            }
        }
    }

    private static void appendFlatRelations(ObjectNode target, ResultSet row, String recordType) {
        String noRawat = valueFromRow(row, "no_rawat");
        String noRkmMedis = valueFromRow(row, "no_rkm_medis");
        String noKtpPasien = firstNonEmpty(valueFromRow(row, "no_ktp"), valueFromRow(row, "nik_pasien"));
        String kdDokter = firstNonEmpty(valueFromRow(row, "kd_dokter"), valueFromRow(row, "nik"), valueFromRow(row, "nip"));
        String ktpDokter = firstNonEmpty(valueFromRow(row, "ktpdokter"), valueFromRow(row, "nik_dokter"));
        String noResep = valueFromRow(row, "no_resep");
        String noOrder = valueFromRow(row, "noorder");
        String kodeBrng = valueFromRow(row, "kode_brng");
        String kdJenisPrw = valueFromRow(row, "kd_jenis_prw");
        String kdPenyakit = valueFromRow(row, "kd_penyakit");
        String kodeProcedure = valueFromRow(row, "kode");

        putIfNotEmpty(target, "encounter_external_id", noRawat);
        putIfNotEmpty(target, "patient_external_id", noRkmMedis);
        putIfNotEmpty(target, "patient_nik", noKtpPasien);
        putIfNotEmpty(target, "practitioner_external_id", kdDokter);
        putIfNotEmpty(target, "practitioner_nik", ktpDokter);
        putIfNotEmpty(target, "prescription_external_id", noResep);
        putIfNotEmpty(target, "order_external_id", noOrder);
        putIfNotEmpty(target, "medication_external_id", kodeBrng);
        putIfNotEmpty(target, "procedure_external_id", kodeProcedure);
        putIfNotEmpty(target, "diagnosis_external_id", kdPenyakit);
        putIfNotEmpty(target, "service_external_id", kdJenisPrw);
    }

    private static void appendFlatFinancial(ObjectNode target, ObjectNode financial) {
        if (target == null || financial == null) {
            return;
        }

        appendFinancialRowsByTable(target, financial.path("direct"));
        appendFinancialRowsByTable(target, financial.path("reference_prices"));
    }

    private static void appendFinancialRowsByTable(ObjectNode target, JsonNode rows) {
        if (target == null || rows == null || !rows.isArray()) {
            return;
        }

        for (int i = 0; i < rows.size(); i++) {
            JsonNode row = rows.get(i);
            if (row == null || !row.isObject()) {
                continue;
            }

            String tableName = textAt(row, "source_table");
            if (tableName.equals("")) {
                continue;
            }

            ensureArray(target, tableName).add(copyWithoutSourceTable(row));
        }
    }

    private static ArrayNode ensureArray(ObjectNode target, String fieldName) {
        JsonNode existing = target.path(fieldName);
        if (existing != null && existing.isArray()) {
            return (ArrayNode) existing;
        }

        ArrayNode rows = JSON_MAPPER.createArrayNode();
        target.set(fieldName, rows);
        return rows;
    }

    private static ObjectNode copyWithoutSourceTable(JsonNode row) {
        ObjectNode clean = JSON_MAPPER.createObjectNode();
        if (row == null || !row.isObject()) {
            return clean;
        }

        Iterator<Map.Entry<String, JsonNode>> iterator = row.fields();
        while (iterator.hasNext()) {
            Map.Entry<String, JsonNode> entry = iterator.next();
            if ("source_table".equals(entry.getKey())) {
                continue;
            }
            clean.set(entry.getKey(), entry.getValue() == null ? null : entry.getValue().deepCopy());
        }
        return clean;
    }

    private static void appendFlattenedSourceFields(ObjectNode target, JsonNode source) {
        if (target == null || source == null) {
            return;
        }

        ObjectNode fields = flattenJson(source);
        Iterator<Map.Entry<String, JsonNode>> iterator = fields.fields();
        while (iterator.hasNext()) {
            Map.Entry<String, JsonNode> entry = iterator.next();
            String key = uniqueFlatKey(target, "source_" + entry.getKey());
            JsonNode value = entry.getValue();
            if (value == null || value.isNull()) {
                target.putNull(key);
            } else {
                target.set(key, value.deepCopy());
            }
        }
    }

    private static void putJsonString(ObjectNode target, String key, JsonNode value) {
        if (target == null || key == null || key.trim().equals("")) {
            return;
        }
        if (value == null || value.isMissingNode() || value.isNull()) {
            target.put(key, "[]");
        } else {
            target.put(key, value.toString());
        }
    }

    private static String buildFlatExternalId(String recordType, String method, ResultSet row) {
        String source = firstNonEmpty(
                valueFromRow(row, "no_rawat"),
                valueFromRow(row, "noorder"),
                valueFromRow(row, "no_resep"),
                valueFromRow(row, "kode_brng"),
                valueFromRow(row, "kd_jenis_prw"),
                valueFromRow(row, "kd_penyakit"),
                valueFromRow(row, "kode")
        );
        String suffix = firstNonEmpty(
                valueFromRow(row, "kode_brng"),
                valueFromRow(row, "kd_jenis_prw"),
                valueFromRow(row, "id_template"),
                valueFromRow(row, "kd_penyakit"),
                valueFromRow(row, "kode"),
                valueFromRow(row, "jam_rawat"),
                valueFromRow(row, "jam"),
                valueFromRow(row, "jam_reg")
        );
        String raw = safe(recordType).toLowerCase() + ":" + safe(method).toLowerCase() + ":" + source + (suffix.equals("") ? "" : ":" + suffix);
        return raw.replace(" ", "_");
    }

    private static String valueFromRow(ResultSet row, String... fieldNames) {
        if (row == null || fieldNames == null) {
            return "";
        }

        for (int i = 0; i < fieldNames.length; i++) {
            String requested = normalizeFlatKey(fieldNames[i]);
            if (requested.equals("")) {
                continue;
            }

            try {
                ResultSetMetaData meta = row.getMetaData();
                for (int col = 1; col <= meta.getColumnCount(); col++) {
                    String label = normalizeFlatKey(firstNonEmpty(meta.getColumnLabel(col), meta.getColumnName(col)));
                    if (requested.equals(label)) {
                        String value = row.getString(col);
                        if (value != null && !value.trim().equals("")) {
                            return value.trim();
                        }
                    }
                }
            } catch (Exception ignored) {
            }
        }
        return "";
    }

    private static String normalizeFlatKey(String key) {
        if (key == null) {
            return "";
        }
        key = key.trim().toLowerCase();
        key = key.replaceAll("[^a-z0-9_]+", "_");
        key = key.replaceAll("_+", "_");
        while (key.startsWith("_")) {
            key = key.substring(1);
        }
        while (key.endsWith("_")) {
            key = key.substring(0, key.length() - 1);
        }
        return key;
    }

    private static String uniqueFlatKey(ObjectNode target, String baseKey) {
        String key = normalizeFlatKey(baseKey);
        if (key.equals("")) {
            key = "field";
        }
        String candidate = key;
        int index = 2;
        while (target.has(candidate)) {
            candidate = key + "_" + index;
            index++;
        }
        return candidate;
    }

    private static ObjectNode buildCanonicalData(String recordType, JsonNode source) {
        ObjectNode data = JSON_MAPPER.createObjectNode();
        putIfNotEmpty(data, "id", textAt(source, "id"));
        putIfNotEmpty(data, "status", textAt(source, "status"));
        putIfNotEmpty(data, "intent", textAt(source, "intent"));
        putIfNotEmpty(data, "priority", textAt(source, "priority"));
        putIfNotEmpty(data, "title", textAt(source, "title"));
        putIfNotEmpty(data, "description", textAt(source, "description"));
        putIfNotEmpty(data, "text", textAt(source.path("text"), "div"));

        putIfNotEmpty(data, "no_rawat", extractNoRawat(source));
        putIfNotEmpty(data, "no_resep", extractNoResep(source));
        putIfNotEmpty(data, "noorder", extractNoOrder(source));
        putIfNotEmpty(data, "kode_brng", extractKodeBrng(source));
        putIfNotEmpty(data, "detail_key", extractDetailKey(source));

        putIfNotEmpty(data, "subject_reference", referenceAt(source.path("subject")));
        putIfNotEmpty(data, "subject_display", textAt(source.path("subject"), "display"));
        putIfNotEmpty(data, "patient_reference", referenceAt(source.path("patient")));
        putIfNotEmpty(data, "patient_display", textAt(source.path("patient"), "display"));
        putIfNotEmpty(data, "encounter_reference", referenceAt(source.path("encounter")));
        putIfNotEmpty(data, "encounter_display", textAt(source.path("encounter"), "display"));
        putIfNotEmpty(data, "requester_reference", referenceAt(source.path("requester")));
        putIfNotEmpty(data, "requester_display", textAt(source.path("requester"), "display"));
        putIfNotEmpty(data, "performer_reference", firstReferenceFromArray(source.path("performer")));
        putIfNotEmpty(data, "service_provider_reference", referenceAt(source.path("serviceProvider")));
        putIfNotEmpty(data, "medication_reference", referenceAt(source.path("medicationReference")));

        putIfNotEmpty(data, "authored_on", textAt(source, "authoredOn"));
        putIfNotEmpty(data, "effective_datetime", textAt(source, "effectiveDateTime"));
        putIfNotEmpty(data, "performed_datetime", textAt(source, "performedDateTime"));
        putIfNotEmpty(data, "issued", textAt(source, "issued"));
        putIfNotEmpty(data, "recorded_date", textAt(source, "recordedDate"));
        putIfNotEmpty(data, "occurrence_datetime", textAt(source, "occurrenceDateTime"));
        putIfNotEmpty(data, "onset_datetime", textAt(source, "onsetDateTime"));

        ObjectNode mainCode = firstCodeableSummary(source);
        if (mainCode.size() > 0) {
            data.set("main_code", mainCode);
        }

        ObjectNode value = valueSummary(source);
        if (value.size() > 0) {
            data.set("value", value);
        }

        data.set("identifiers", canonicalIdentifiers(source));
        data.set("codes", collectCodingSummaries(source));
        data.set("references", collectReferenceSummaries(source));
        data.set("fields", flattenJson(source));
        return data;
    }

    private static ObjectNode buildCanonicalRelations(JsonNode source) {
        ObjectNode relations = JSON_MAPPER.createObjectNode();
        putIfNotEmpty(relations, "subject", referenceAt(source.path("subject")));
        putIfNotEmpty(relations, "patient", firstNonEmpty(referenceAt(source.path("patient")), referenceAt(source.path("subject"))));
        putIfNotEmpty(relations, "encounter", referenceAt(source.path("encounter")));
        putIfNotEmpty(relations, "requester", referenceAt(source.path("requester")));
        putIfNotEmpty(relations, "service_provider", referenceAt(source.path("serviceProvider")));
        putIfNotEmpty(relations, "medication", firstNonEmpty(referenceAt(source.path("medicationReference")), referenceAt(source.path("medication"))));
        putIfNotEmpty(relations, "specimen", firstReferenceFromArray(source.path("specimen")));
        putIfNotEmpty(relations, "based_on", firstReferenceFromArray(source.path("basedOn")));
        putIfNotEmpty(relations, "part_of", firstReferenceFromArray(source.path("partOf")));
        putIfNotEmpty(relations, "performer", firstReferenceFromArray(source.path("performer")));
        putIfNotEmpty(relations, "result", firstReferenceFromArray(source.path("result")));

        ArrayNode allReferences = collectReferenceSummaries(source);
        relations.set("all_references", allReferences);
        relations.put("reference_count", allReferences.size());
        return relations;
    }

    private static ObjectNode flattenJson(JsonNode source) {
        ObjectNode fields = JSON_MAPPER.createObjectNode();
        addFlattenedJson(fields, "", source);
        return fields;
    }

    private static void addFlattenedJson(ObjectNode target, String path, JsonNode node) {
        if (target == null || node == null || node.isMissingNode()) {
            return;
        }

        if (node.isObject()) {
            Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
            if (!fields.hasNext() && !path.equals("")) {
                target.set(path, node.deepCopy());
            }
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> entry = fields.next();
                String childPath = path.equals("") ? entry.getKey() : path + "." + entry.getKey();
                addFlattenedJson(target, childPath, entry.getValue());
            }
            return;
        }

        if (node.isArray()) {
            if (node.size() == 0 && !path.equals("")) {
                target.set(path, node.deepCopy());
            }
            for (int i = 0; i < node.size(); i++) {
                addFlattenedJson(target, path + "[" + i + "]", node.get(i));
            }
            return;
        }

        if (path.equals("")) {
            path = "value";
        }
        target.set(path, node.deepCopy());
    }

    private static ArrayNode canonicalIdentifiers(JsonNode source) {
        ArrayNode identifiers = JSON_MAPPER.createArrayNode();
        JsonNode identifier = source == null ? null : source.path("identifier");
        if (!identifier.isArray()) {
            return identifiers;
        }

        for (int i = 0; i < identifier.size(); i++) {
            JsonNode item = identifier.get(i);
            ObjectNode row = JSON_MAPPER.createObjectNode();
            row.put("index", i);
            putIfNotEmpty(row, "system", textAt(item, "system"));
            putIfNotEmpty(row, "value", textAt(item, "value"));
            putIfNotEmpty(row, "use", textAt(item, "use"));
            putIfNotEmpty(row, "type_text", textAt(item.path("type"), "text"));
            identifiers.add(row);
        }
        return identifiers;
    }

    private static ArrayNode collectCodingSummaries(JsonNode source) {
        ArrayNode codings = JSON_MAPPER.createArrayNode();
        collectCodings(source, "", codings);
        return codings;
    }

    private static void collectCodings(JsonNode node, String path, ArrayNode codings) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return;
        }

        if (node.isObject()) {
            JsonNode coding = node.path("coding");
            if (coding.isArray()) {
                for (int i = 0; i < coding.size(); i++) {
                    JsonNode item = coding.get(i);
                    ObjectNode row = JSON_MAPPER.createObjectNode();
                    row.put("path", path.equals("") ? "coding[" + i + "]" : path + ".coding[" + i + "]");
                    putIfNotEmpty(row, "system", textAt(item, "system"));
                    putIfNotEmpty(row, "code", textAt(item, "code"));
                    putIfNotEmpty(row, "display", textAt(item, "display"));
                    putIfNotEmpty(row, "text", textAt(node, "text"));
                    codings.add(row);
                }
            }

            Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> entry = fields.next();
                String childPath = path.equals("") ? entry.getKey() : path + "." + entry.getKey();
                collectCodings(entry.getValue(), childPath, codings);
            }
            return;
        }

        if (node.isArray()) {
            for (int i = 0; i < node.size(); i++) {
                collectCodings(node.get(i), path + "[" + i + "]", codings);
            }
        }
    }

    private static ArrayNode collectReferenceSummaries(JsonNode source) {
        ArrayNode references = JSON_MAPPER.createArrayNode();
        collectReferences(source, "", references);
        return references;
    }

    private static void collectReferences(JsonNode node, String path, ArrayNode references) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return;
        }

        if (node.isObject()) {
            String reference = textAt(node, "reference");
            if (!reference.equals("")) {
                ObjectNode row = JSON_MAPPER.createObjectNode();
                row.put("path", path);
                row.put("reference", reference);
                putIfNotEmpty(row, "display", textAt(node, "display"));
                putIfNotEmpty(row, "type", textAt(node, "type"));
                references.add(row);
            }

            Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> entry = fields.next();
                String childPath = path.equals("") ? entry.getKey() : path + "." + entry.getKey();
                collectReferences(entry.getValue(), childPath, references);
            }
            return;
        }

        if (node.isArray()) {
            for (int i = 0; i < node.size(); i++) {
                collectReferences(node.get(i), path + "[" + i + "]", references);
            }
        }
    }

    private static ObjectNode firstCodeableSummary(JsonNode source) {
        JsonNode codeable = firstExistingNode(
                source.path("code"),
                source.path("vaccineCode"),
                source.path("medicationCodeableConcept")
        );
        return codeableSummary(codeable);
    }

    private static ObjectNode codeableSummary(JsonNode codeable) {
        ObjectNode summary = JSON_MAPPER.createObjectNode();
        if (codeable == null || codeable.isMissingNode() || codeable.isNull()) {
            return summary;
        }

        putIfNotEmpty(summary, "text", textAt(codeable, "text"));
        JsonNode coding = codeable.path("coding");
        if (coding.isArray() && coding.size() > 0) {
            JsonNode first = coding.get(0);
            putIfNotEmpty(summary, "system", textAt(first, "system"));
            putIfNotEmpty(summary, "code", textAt(first, "code"));
            putIfNotEmpty(summary, "display", textAt(first, "display"));
        }
        return summary;
    }

    private static ObjectNode valueSummary(JsonNode source) {
        ObjectNode summary = JSON_MAPPER.createObjectNode();
        if (source == null) {
            return summary;
        }

        JsonNode quantity = source.path("valueQuantity");
        if (quantity.isObject()) {
            summary.put("type", "quantity");
            putIfNotEmpty(summary, "value", textAt(quantity, "value"));
            putIfNotEmpty(summary, "unit", textAt(quantity, "unit"));
            putIfNotEmpty(summary, "system", textAt(quantity, "system"));
            putIfNotEmpty(summary, "code", textAt(quantity, "code"));
            return summary;
        }

        String value = firstNonEmpty(
                textAt(source, "valueString"),
                textAt(source, "valueInteger"),
                textAt(source, "valueDecimal"),
                textAt(source, "valueBoolean"),
                textAt(source, "valueDateTime")
        );
        if (!value.equals("")) {
            summary.put("type", "scalar");
            summary.put("value", value);
            return summary;
        }

        JsonNode codeable = source.path("valueCodeableConcept");
        if (codeable.isObject()) {
            summary.put("type", "codeable_concept");
            summary.set("code", codeableSummary(codeable));
        }
        return summary;
    }

    private static JsonNode firstExistingNode(JsonNode... nodes) {
        if (nodes == null) {
            return null;
        }
        for (int i = 0; i < nodes.length; i++) {
            JsonNode node = nodes[i];
            if (node != null && !node.isMissingNode() && !node.isNull()) {
                if (node.isObject() && node.size() == 0) {
                    continue;
                }
                return node;
            }
        }
        return null;
    }

    private static String firstReferenceFromArray(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return "";
        }

        if (node.isArray()) {
            for (int i = 0; i < node.size(); i++) {
                String reference = referenceAt(node.get(i));
                if (!reference.equals("")) {
                    return reference;
                }
            }
            return "";
        }

        return referenceAt(node);
    }

    private static HttpHeaders buildAckHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return headers;
    }

    private static String buildKhanzaAckBody(JsonNode fhir, String resourceType, String externalId) {
        ObjectNode ack;
        if (fhir != null && fhir.isObject()) {
            ack = (ObjectNode) fhir.deepCopy();
        } else {
            ack = JSON_MAPPER.createObjectNode();
        }

        ack.put("resourceType", resourceType);
        ack.put("id", buildStableAckId(fhir, externalId));
        return ack.toString();
    }

    private static String buildStableAckId(JsonNode fhir, String externalId) {
        String fhirId = textAt(fhir, "id");
        if (!fhirId.equals("")) {
            return fhirId;
        }

        return UUID.nameUUIDFromBytes(
                ("khanza-erpnext-canonical:" + externalId).getBytes(StandardCharsets.UTF_8)
        ).toString();
    }

    private static String buildExternalId(
            String method,
            String endpointPath,
            JsonNode fhir,
            String resourceType
    ) {
        String stableSource = firstNonEmpty(
                collectIdentifierSource(fhir),
                textAt(fhir, "id"),
                extractBusinessReference(fhir),
                endpointPath
        );

        String source = resourceType
                + "|" + safe(method)
                + "|" + safe(endpointPath)
                + "|" + stableSource;

        String uuid = UUID.nameUUIDFromBytes(source.getBytes(StandardCharsets.UTF_8)).toString();
        return resourceType + "-" + uuid;
    }

    private static String extractBusinessReference(JsonNode fhir) {
        if (fhir == null) {
            return "";
        }

        StringBuilder source = new StringBuilder();
        appendReferenceSource(source, "subject", fhir.path("subject"));
        appendReferenceSource(source, "patient", fhir.path("patient"));
        appendReferenceSource(source, "encounter", fhir.path("encounter"));
        appendReferenceSource(source, "requester", fhir.path("requester"));
        appendReferenceSource(source, "medicationReference", fhir.path("medicationReference"));
        appendDateSource(source, "authoredOn", fhir.path("authoredOn"));
        appendDateSource(source, "effectiveDateTime", fhir.path("effectiveDateTime"));
        appendDateSource(source, "performedDateTime", fhir.path("performedDateTime"));
        appendDateSource(source, "issued", fhir.path("issued"));
        appendDateSource(source, "recordedDate", fhir.path("recordedDate"));
        appendDateSource(source, "occurrenceDateTime", fhir.path("occurrenceDateTime"));

        String code = collectCodingSource(fhir.path("code"));
        if (code.equals("")) {
            code = collectCodingSource(fhir.path("vaccineCode"));
        }
        if (code.equals("")) {
            code = collectCodingSource(fhir.path("medicationCodeableConcept"));
        }
        if (!code.equals("")) {
            appendPart(source, "code=" + code);
        }

        return source.toString();
    }

    private static void appendReferenceSource(StringBuilder source, String label, JsonNode node) {
        if (node == null || !node.isObject()) {
            return;
        }

        String reference = textAt(node, "reference");
        if (!reference.equals("")) {
            appendPart(source, label + "=" + reference);
        }
    }

    private static void appendDateSource(StringBuilder source, String label, JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return;
        }

        String value = node.asText();
        if (value != null && !value.trim().equals("")) {
            appendPart(source, label + "=" + value.trim());
        }
    }

    private static String collectCodingSource(JsonNode codeable) {
        if (codeable == null || codeable.isMissingNode() || codeable.isNull()) {
            return "";
        }

        JsonNode coding = codeable.path("coding");
        if (coding.isArray() && coding.size() > 0) {
            JsonNode firstCoding = coding.get(0);
            return textAt(firstCoding, "system") + "#" + textAt(firstCoding, "code");
        }

        return textAt(codeable, "text");
    }

    private static void appendPart(StringBuilder source, String value) {
        if (value == null || value.trim().equals("")) {
            return;
        }

        if (source.length() > 0) {
            source.append("|");
        }
        source.append(value.trim());
    }

    private static String collectIdentifierSource(JsonNode fhir) {
        if (fhir == null) {
            return "";
        }

        JsonNode identifier = fhir.path("identifier");
        if (!identifier.isArray() || identifier.size() == 0) {
            return "";
        }

        StringBuilder source = new StringBuilder();
        for (int i = 0; i < identifier.size(); i++) {
            JsonNode item = identifier.get(i);
            if (source.length() > 0) {
                source.append("|");
            }
            source.append(textAt(item, "system")).append("#").append(textAt(item, "value"));
        }

        return source.toString();
    }

    private static String buildEndpointPath(URI uri, String method, JsonNode fhir, String resourceType) {
        if ("PUT".equalsIgnoreCase(method)) {
            String id = textAt(fhir, "id");
            if (id.equals("")) {
                id = extractResourceIdFromPath(uri, resourceType);
            }
            if (!id.equals("")) {
                return "/" + resourceType + "/" + id;
            }
        }

        return "/" + resourceType;
    }

    private static String firstIdentifierValue(JsonNode fhir) {
        if (fhir == null) {
            return "";
        }

        JsonNode identifier = fhir.path("identifier");
        if (identifier.isArray() && identifier.size() > 0) {
            return textAt(identifier.get(0), "value");
        }

        return "";
    }

    private static String extractResourceType(JsonNode fhir) {
        return firstNonEmpty(
                textAt(fhir, "resourceType"),
                textAt(fhir, "resource_type")
        );
    }

    private static String extractResourceTypeFromPath(URI uri) {
        if (uri == null || uri.getPath() == null) {
            return "";
        }

        String[] segments = uri.getPath().split("/");
        boolean afterFhirMarker = false;
        String firstPossibleResource = "";

        for (int i = 0; i < segments.length; i++) {
            String segment = segments[i];
            if (segment == null || segment.trim().equals("")) {
                continue;
            }

            if (isFhirMarkerSegment(segment)) {
                afterFhirMarker = true;
                continue;
            }

            if (isVersionSegment(segment)) {
                continue;
            }

            if (afterFhirMarker) {
                return segment;
            }

            if (firstPossibleResource.equals("")) {
                firstPossibleResource = segment;
            }
        }

        return firstPossibleResource;
    }

    private static boolean isFhirMarkerSegment(String segment) {
        if (segment == null) {
            return false;
        }

        String lower = segment.toLowerCase();
        return lower.equals("fhir-r4") || lower.equals("r4");
    }

    private static boolean isVersionSegment(String segment) {
        if (segment == null) {
            return false;
        }

        return segment.toLowerCase().matches("v[0-9]+");
    }

    private static String extractResourceIdFromPath(URI uri, String resourceType) {
        if (uri == null || uri.getPath() == null || resourceType == null || resourceType.trim().equals("")) {
            return "";
        }

        String[] segments = uri.getPath().split("/");
        for (int i = 0; i < segments.length - 1; i++) {
            if (resourceType.equalsIgnoreCase(segments[i])) {
                return segments[i + 1] == null ? "" : segments[i + 1];
            }
        }

        return "";
    }

    private static JsonNode parseJsonQuietly(String value) {
        if (value == null || value.trim().equals("")) {
            return null;
        }

        try {
            return JSON_MAPPER.readTree(value);
        } catch (Exception ignored) {
            return null;
        }
    }

    private static String textAt(JsonNode node, String fieldName) {
        if (node == null || fieldName == null || !node.has(fieldName)) {
            return "";
        }

        String value = node.path(fieldName).asText();
        return value == null ? "" : value.trim();
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }

    private static String firstNonEmpty(String... values) {
        if (values == null) {
            return "";
        }

        for (int i = 0; i < values.length; i++) {
            if (values[i] != null && !values[i].trim().equals("")) {
                return values[i].trim();
            }
        }

        return "";
    }

    private static boolean isTokenUrl(URI uri) {
        if (uri == null) {
            return false;
        }

        String url = uri.toString().toLowerCase();
        return url.contains("accesstoken")
                || url.contains("oauth")
                || url.contains("token");
    }
}
