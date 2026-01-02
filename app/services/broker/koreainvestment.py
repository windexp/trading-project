import logging
logger = logging.getLogger(__name__)
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import ssl
import json
import yaml
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.services.broker.base import BaseBroker
import enum
from app.models.enums import RequestOutcome, OrderStatus

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )
class KoreaInvestmentBroker(BaseBroker):

    def parse_order_response(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize KIS order response to unified format.
        """
        output = raw.get('output', {}) if raw else {}
        order_id = output.get('ODNO')
        order_time = output.get('ORD_TMD')
        req_outcome = RequestOutcome.ACCEPTED if raw and raw.get('rt_cd') == '0' and order_id else RequestOutcome.REJECTED
        # KIS: rejected if rt_cd != '0' or order_id missing
        is_holiday = (
            req_outcome == RequestOutcome.REJECTED and 
            (
                '휴장' in raw.get('msg1', '') or
                '주문시간 외 불가' in raw.get('msg1', '')
            )
        )
        return {
            'outcome': req_outcome,
            'order_id': order_id,
            'error_code': raw.get('rt_cd', ''),
            'error_msg': raw.get('msg1', ''),
            'raw': raw,
            'is_holiday': is_holiday  # KIS does not provide this info directly
        }

    def parse_price_response(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        price = None
        if raw and 'output' in raw and 'price' in raw['output']:
            try:
                output= raw['output']   
                price = float(output['last'])
                base=float(output['base'])
                high = float(output.get('high', price))
                low = float(output.get('low', price))
                open_price = float(output.get('open', price))
            except Exception:
                price = None
        return {'price': price, 'high': high, 'low': low, 'base': base, 'open': open_price, 'raw': raw}

    def parse_history_response(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Return list of dicts with at least: order_id, status, filled_qty, ord_qty, etc.
        output = raw.get('output', [])
        normalized = []
        for h in output:
            filled_qty = int(h.get('ft_ccld_qty', 0))
            order_qty = int(h.get('ft_ord_qty', 0))
            if h.get('prcs_stat_name') == '완료':
                if h.get('rvse_cncl') == '취소':
                    order_status = OrderStatus.CANCELLED
                elif filled_qty == order_qty and filled_qty > 0:
                    order_status = OrderStatus.FILLED
                elif filled_qty > 0 and filled_qty < order_qty:
                    order_status = OrderStatus.PARTIALLY_FILLED
                elif filled_qty == 0:
                    order_status = OrderStatus.UNFILLED
            elif h.get('prcs_stat_name') == '전송':
                order_status = OrderStatus.SUBMITTED
            elif h.get('prcs_stat_name') == '거부':
                order_status = OrderStatus.REJECTED
            else:
                order_status = OrderStatus.UNFILLED
                logger.info(f"Order {h.get('order_id')} UNFILLED (기타)")
            normalized.append({
                'order_id': h.get('odno'),
                'status': order_status,
                'cancel_type': h.get('rvse_cncl_dvsn_name'),
                'filled_qty': filled_qty,
                'ord_qty': order_qty,
                'filled_amt': round(float(h.get('ft_ccld_amt3', 0.0)), 2),
                'raw': h
            })
        return normalized
    def parse_balance_response(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw balance response from broker into standardized format."""
        pass
    def cancel_order_response(self, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order."""
        pass

    def __init__(self, account_no: str, 
                 app_key: str, 
                 app_secret: str,
                 base_url: str = settings.KIS_BASE_URL):
        
        self.account_no = account_no
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url
        
        self.access_token = None
        self.token_expiry = None

        # Setup Session with TLS 1.2+ enforcement
        self.session = requests.Session()
        adapter = TLSAdapter()
        self.session.mount("https://", adapter)
        
        # Load API Config from YAML
        try:
            # Construct path relative to this file (app/services/broker/api_config.yaml)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "api_config.yaml")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # Use overseas config
            self.api_map = config.get('oversea', {}).get('api_map', {})
            
            # Ensure URLs have leading slash
            for key, val in self.api_map.items():
                if not val['url'].startswith('/'):
                    val['url'] = '/' + val['url']
            
            # Add Token Endpoint (not in yaml usually)
            self.api_map["token"] = {"url": "/oauth2/tokenP", "tr_id": ""}
            logger.debug(f"✅ Loaded API Config from {config_path}")

            # Load Tickers and Exchange Maps
            tickers_path = os.path.join(current_dir, "tickers.yaml")
            maps_path = os.path.join(current_dir, "exchange_maps.yaml")
            
            with open(tickers_path, 'r', encoding='utf-8') as f:
                self.tickers = yaml.safe_load(f)
            
            with open(maps_path, 'r', encoding='utf-8') as f:
                self.exchange_maps = yaml.safe_load(f)
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to load config/data files: {e}")
            # Fallback to hardcoded map
            self.api_map = {
                "token": {"url": "/oauth2/tokenP", "tr_id": ""},
                "price": {"url": "/uapi/overseas-price/v1/quotations/price-detail", "tr_id": "HHDFS76200200"},
                "dailyprice": {"url": "/uapi/overseas-price/v1/quotations/dailyprice", "tr_id": "HHDFS76240000"},
                "balance": {"url": "/uapi/overseas-stock/v1/trading/inquire-balance", "tr_id": "TTTS3012R"},
                "buy": {"url": "/uapi/overseas-stock/v1/trading/order", "tr_id": "TTTT1002U"},
                "sell": {"url": "/uapi/overseas-stock/v1/trading/order", "tr_id": "TTTT1006U"},
                "transaction": {"url": "/uapi/overseas-stock/v1/trading/inquire-ccnl", "tr_id": "TTTS3035R"},
            }
            self.tickers = {}
            self.exchange_maps = {"order_map": {"NAS": "NASD", "NYS": "NYSE", "AMS": "AMEX"}}
        
        # Initial Token Generation
        self._ensure_token()

    def _ensure_token(self):
        """Check if token is valid, otherwise regenerate."""
        # 1. Check Memory
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return

        # 2. Check File Cache
        cache_file = "token_cache.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cache = json.load(f)
                    
                    # Check if token belongs to this App Key
                    if cache.get("app_key") == self.app_key:
                        issued_at = datetime.fromisoformat(cache["issued_at"])
                        # Check if within 12 hours
                        if datetime.now() - issued_at < timedelta(hours=12):
                            self.access_token = cache["access_token"]
                            self.token_expiry = issued_at + timedelta(hours=12)
                            # logger.info(f"✅ Loaded KIS Access Token from Cache (Issued: {issued_at})")
                            return
            except Exception as e:
                # logger.warning(f"⚠️ Failed to load token cache: {e}")
                pass

        # 3. Request New Token
        url = f"{self.base_url}{self.api_map['token']['url']}"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            res = self.session.post(url, headers=headers, json=body)
            data = res.json()
            if "access_token" in data:
                self.access_token = data["access_token"]
                issued_at = datetime.now()
                self.token_expiry = issued_at + timedelta(hours=12)
                logger.info(f"✅ KIS Access Token Generated (Issued: {issued_at})")
                
                # Save to Cache
                with open(cache_file, "w") as f:
                    json.dump({
                        "access_token": self.access_token,
                        "issued_at": issued_at.isoformat(),
                        "app_key": self.app_key
                    }, f)
                
                # Secure the file
                try:
                    os.chmod(cache_file, 0o600)
                except:
                    pass
            else:
                logger.error(f"❌ Failed to generate token: {data}")
                raise ValueError("Token generation failed")
        except Exception as e:
            logger.error(f"❌ Token request error: {e}")
            raise

    def _get_headers(self, tr_id: str) -> Dict[str, str]:
        self._ensure_token()
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P"
        }

    def _send_request(self, api_name: str, method: str = "GET", params: Dict = None, data: Dict = None, nt=None) -> Dict:
        if api_name not in self.api_map:
            raise ValueError(f"Unknown API: {api_name}")
            
        config = self.api_map[api_name]
        url = f"{self.base_url}{config['url']}"
        headers = self._get_headers(config["tr_id"])
        if nt is not None:
            headers[nt[0]]=nt[1]
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, params=params)
            elif method == "POST":
                response = self.session.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code != 200:
                logger.warning(f"⚠️ API Error ({response.status_code}): {response.text}")
                return {}
                
            res_json = response.json()
            if res_json.get('rt_cd') != '0':
                logger.warning(f"⚠️ KIS Error: {res_json.get('msg1')}")
                return res_json
                
            return res_json
            
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return {}

    def get_exchange_code(self, ticker: str) -> str:
        """
        Get the internal exchange code for a ticker (e.g., NAS, NYS, AMS).
        Uses tickers.yaml for lookup.
        """
        ticker = ticker.upper()
        if hasattr(self, 'tickers') and ticker in self.tickers:
            return self.tickers[ticker]
        return "NAS" # Default fallback

    def get_order_exchange_code(self, ticker: str) -> str:
        """
        Get the exchange code required for ORDER APIs (e.g., NASD, NYSE, AMEX).
        Uses exchange_maps.yaml to map internal code -> order code.
        """
        internal_code = self.get_exchange_code(ticker)
        if hasattr(self, 'exchange_maps') and 'order_map' in self.exchange_maps:
            return self.exchange_maps['order_map'].get(internal_code, internal_code)
        return "NASD" # Default fallback

    def get_balance(self) -> Dict[str, Any]:
        # Split account no: 12345678-01 -> 12345678, 01
        cano, prdt = self.account_no.split('-')
        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt,
            "OVRS_EXCG_CD": "NASD", # Default
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        return self._send_request("balance", method="GET", params=params)

    def get_price(self, ticker: str) -> Dict[str, Any]:
        params = {
            "AUTH": "",
            "EXCD": self.get_exchange_code(ticker),
            "SYMB": ticker.upper()
        }
        res = self._send_request("price", method="GET", params=params)
        if res and 'output' in res and 'last' in res['output']:
            res['output']['price'] = res['output']['last']
        return res

    def _get_order_type_code(self, order_type: str) -> str:
        """Map friendly order type names to KIS API codes."""
        mapping = {
            "MOO": "31", # Market On Open
            "LOO": "32", # Limit On Open
            "MOC": "33", # Market On Close
            "LOC": "34", # Limit On Close
            
            "MARKET": "00", # US Market order often uses 00 with price 0, or specific code depending on broker setup. 
                            # Safest is usually Limit. But if user sends "MARKET", we might need to handle price=0.
                            # For now, let's assume explicit codes or these keys.
            "00": "00",
            "31": "31",
            "32": "32",
            "33": "33",
            "34": "34"
        }
        return mapping.get(order_type.upper(), "00") # Default to Limit

    def buy_order(self, ticker: str, quantity: int, price: float, order_type: str = "00") -> Dict[str, Any]:
        cano, prdt = self.account_no.split('-')
        
        dvsn = self._get_order_type_code(order_type)
        
        data = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt,
            "OVRS_EXCG_CD": self.get_order_exchange_code(ticker),
            "PDNO": ticker.upper(),
            "ORD_QTY": str(quantity),
            "OVRS_ORD_UNPR": f"{price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": dvsn
        }
        # print(f"DEBUG: Buy Order Payload: {data}")
        return self._send_request("buy", method="POST", data=data)

    def sell_order(self, ticker: str, quantity: int, price: float, order_type: str = "00") -> Dict[str, Any]:
        cano, prdt = self.account_no.split('-')
        
        dvsn = self._get_order_type_code(order_type)
        
        data = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt,
            "OVRS_EXCG_CD": self.get_order_exchange_code(ticker),
            "PDNO": ticker.upper(),
            "ORD_QTY": str(quantity),
            "OVRS_ORD_UNPR": f"{price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": dvsn
        }
        return self._send_request("sell", method="POST", data=data)

    def get_transaction_history(self, ticker: str, start_date: str, end_date: str) -> dict:
        cano, prdt = self.account_no.split('-')
        # 전체 조회 시 빈 문자열로
        if ticker:
            pdno = ticker.upper()
            ovrs_excg_cd = self.get_order_exchange_code(ticker)
        else:
            pdno = ""
            ovrs_excg_cd = ""
        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt,
            "OVRS_EXCG_CD": ovrs_excg_cd,
            "PDNO": pdno,
            "ORD_STRT_DT": start_date,
            "ORD_END_DT": end_date,
            "SLL_BUY_DVSN": "00",
            "CCLD_NCCS_DVSN": "00",
            "SORT_SQN": "DS",
            "ORD_DT": "",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        loop = 1
        # print(f"DEBUG: Page loop - {loop}")
        # print(f"DEBUG: INPUT CTX_AREA_FK200: {params['CTX_AREA_FK200']}")
        # print(f"DEBUG: INPUT CTX_AREA_NK200: {params['CTX_AREA_NK200']}")
        res = self._send_request("transaction", method="GET", params=params)
        output = res.get("output", [])
        # print(f"DEBUG: OUTPUT tr_cont: {res['tr_cont']}")
        # print(f"DEBUG: OUTPUT CTX_AREA_FK200: {res.get('ctx_area_fk200')}")
        # print(f"DEBUG: OUTPUT CTX_AREA_NK200: {res.get('ctx_area_nk200')}")
        # print(f"DEBUG: MSG1:  {res.get('msg1')}")
        
        while not res["ctx_area_nk200"].strip() == "" and loop < 5:
            params["CTX_AREA_NK200"] = res["ctx_area_nk200"]
            params["CTX_AREA_FK200"] = res["ctx_area_fk200"]

            loop += 1
            res = self._send_request("transaction", params=params, nt=["tr_cont","N"])
            new_output = res.get("output", [])
            # print(f"DEBUG: OUTPUT tr_cont: {res['tr_cont']}")

            if not new_output:
                # print(f"[PAGE {loop}] No new output, breaking loop.")
                break
            output += new_output
        # for out in output:
        #     print(f"DEBUG: Transaction: {out['rvse_cncl_dvsn_name']}")
        return {"output": output}

