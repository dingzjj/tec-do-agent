import java.util.Map;
import java.util.HashMap;
import java.util.List;
import java.util.ArrayList;
import java.util.Collections;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public class OpenSignGenerator {

    public String newSign(String secretKey, Map<String, Object> data) {
        if (secretKey == null || secretKey.isEmpty() || data == null) {
            return "";
        }

        String token = secretKey + loopToken(data);
        return md5(token).toLowerCase();
    }

    private String loopToken(Map<String, Object> params) {
        List<String> encode = new ArrayList<>();
        List<String> keys = new ArrayList<>(params.keySet());
        Collections.sort(keys);

        for (String k : keys) {
            Object v = params.get(k);
            if (v instanceof Map) {
                encode.add(k + "=" + loopToken((Map<String, Object>) v));
            } else if (v instanceof List) {
                continue; // Skip lists
            } else {
                encode.add(k + "=" + v);
            }
        }
        return String.join("", encode);
    }

    private String md5(String input) {
        try {

            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] messageDigest = md.digest(input.getBytes());
            StringBuilder hexString = new StringBuilder();
            for (byte b : messageDigest) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1)
                    hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException(e);
        }
    }

    public static void main(String[] args) {
        // long timestamp = System.currentTimeMillis();
        long timestamp = 1752051243867L;
        System.out.println(timestamp);
        String timestampStr = String.valueOf(timestamp);
        String token = "Rt8pKm2vN5XwQ1jZcF4yHxBsDg7uL9eP";
        String signSecretKey = "0349e0173a87415f8a02c12fd4deef27";
        OpenSignGenerator openSignGenerator = new OpenSignGenerator();
        Map<String, Object> map = new HashMap<>();
        map.put("timestamp", timestampStr);
        map.put("auth-token", token);
        String sign = openSignGenerator.newSign(signSecretKey, map);
        System.out.println(sign);
    }
}
