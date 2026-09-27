"""API for Marstek CT Meter."""
import socket
import re
import logging

_LOGGER = logging.getLogger(__name__)

class MarstekCtApi:
    """API to communicate with the Marstek CT meter."""

    def __init__(self, host, device_type, battery_mac, ct_mac, ct_type):
        self._host = host
        self._port = 12345
        self._device_type = device_type
 
         # MACs formatieren
        self._battery_mac = battery_mac.replace(":", "").upper()
        self._ct_mac = ct_mac.replace(":", "").lower()
 
         # ct_type unverändert übernehmen
        self._ct_type = ct_type
        self._timeout = 5.0
        self._payload = self._build_payload()

    def _build_payload(self, ct_mac=None):
        """Builds the UDP payload for the query."""
        target_ct_mac = ct_mac if ct_mac is not None else self._ct_mac
        SOH, STX, ETX, SEPARATOR = 0x01, 0x02, 0x03, '|'
        message_fields = [self._device_type, self._battery_mac, self._ct_type, target_ct_mac, '0', '0']
        message_bytes = (SEPARATOR + SEPARATOR.join(message_fields)).encode('ascii')
        base_size = 1 + 1 + len(message_bytes) + 1 + 2
        total_length = base_size + 2
        for length_digits in range(1, 5):
            candidate = base_size + length_digits
            if len(str(candidate)) == length_digits:
                total_length = candidate
                break
        payload = bytearray([SOH, STX])
        payload.extend(str(total_length).encode('ascii'))
        payload.extend(message_bytes)
        payload.append(ETX)
        xor = 0
        for b in payload:
            xor ^= b
        payload.extend(f"{xor:02x}".encode('ascii'))
        return payload

    def _decode_response(self, data: bytes):
        """Parses the UDP response."""
        if len(data) < 10:
            return {"error": "Response packet too short"}
        if data[0] != 0x01 or data[1] != 0x02:
            return {"error": "Missing SOH/STX header in response"}

        sep_index = data.find(b'|', 2)
        if sep_index == -1:
            return {"error": "No separator found in response"}

        etx_index = data.rfind(b'\x03')
        if etx_index == -1 or etx_index <= sep_index:
            etx_index = len(data) - 2

        try:
            message = data[sep_index:etx_index].decode('ascii', errors='ignore')
        except Exception as e:
            return {"error": f"Invalid ASCII encoding: {e}"}

        fields = message.split('|')[1:]

        labels = [
            "meter_dev_type", "meter_mac_code", "hhm_dev_type", "hhm_mac_code",
            "A_phase_power", "B_phase_power", "C_phase_power", "total_power",
            "A_chrg_nb", "B_chrg_nb", "C_chrg_nb", "ABC_chrg_nb", "wifi_rssi",
            "info_idx", "x_chrg_power", "A_chrg_power", "B_chrg_power", "C_chrg_power",
            "ABC_chrg_power", "x_dchrg_power", "A_dchrg_power", "B_dchrg_power",
            "C_dchrg_power", "ABC_dchrg_power"
        ]

        parsed = {}
        for i, label in enumerate(labels):
            val = fields[i] if i < len(fields) else None
            try:
                parsed[label] = int(val)
            except (ValueError, TypeError):
                parsed[label] = val

        return parsed

    def fetch_data(self):
        """Fetch data from the meter. This is a blocking call."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self._timeout)
        try:
            sock.sendto(self._payload, (self._host, self._port))
            try:
                response, _ = sock.recvfrom(1024)
                return self._decode_response(response)
            except socket.timeout:
                # If lowercase timed out, retry with uppercase CT MAC
                if self._ct_mac != self._ct_mac.upper():
                    upper_payload = self._build_payload(ct_mac=self._ct_mac.upper())
                    sock.sendto(upper_payload, (self._host, self._port))
                    response, _ = sock.recvfrom(1024)
                    return self._decode_response(response)
                raise
        except socket.timeout:
            return {"error": "Timeout - No response from meter"}
        except Exception as e:
            _LOGGER.warning("An unexpected error occurred: %s", str(e))
            return {"error": f"An unexpected error occurred: {str(e)}"}
        finally:
            sock.close()

    def test_connection(self):
        """A simple blocking call to test connectivity."""
        return self.fetch_data()

class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
