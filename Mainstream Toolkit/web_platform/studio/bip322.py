"""BIP322 simple, Taproot key-path proofs for Xverse ordinal addresses only."""
import base64
from embit import ec, hashes, script
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from embit.networks import NETWORKS


def signing_transaction(address, message):
    output_script = script.address_to_scriptpubkey(address)
    if output_script.script_type() != 'p2tr' or output_script.address(NETWORKS['main']) != address:
        raise ValueError('A mainnet Taproot ordinal address is required.')
    digest = hashes.tagged_hash('BIP0322-signed-message', message.encode())
    spend = Transaction(version=0, vin=[TransactionInput(bytes(32), 0xffffffff,
        script_sig=script.Script(b'\x00\x20' + digest), sequence=0)],
        vout=[TransactionOutput(0, output_script)], locktime=0)
    sign = Transaction(version=0, vin=[TransactionInput(spend.txid(), 0, sequence=0)],
        vout=[TransactionOutput(0, script.Script(b'\x6a'))], locktime=0)
    return sign, output_script


def verify(address, message, signature):
    try:
        sign, output_script = signing_transaction(address, message)
        raw = base64.b64decode(signature[3:] if signature.startswith('smp') else signature, validate=True)
        # Exactly one key-path signature, no annex, script path, or trailing bytes.
        if len(raw) not in (66, 67) or raw[0] != 1 or raw[1] != len(raw) - 2:
            return False
        sig = raw[2:]
        sighash = 0 if len(sig) == 64 else sig[-1]
        if sighash not in (0, 1) or (len(sig) == 65 and sighash == 0):
            return False
        digest = sign.sighash_taproot(0, [output_script], [0], sighash=sighash)
        return ec.PublicKey.from_xonly(output_script.data[2:]).schnorr_verify(ec.SchnorrSig.parse(sig[:64]), digest)
    except Exception:
        return False
