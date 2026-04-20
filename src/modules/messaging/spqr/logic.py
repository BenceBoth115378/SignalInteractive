from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from modules import external as ext
from components.data_classes import (
    AuthenticatorState,
    BraidProtocolState,
    DecoderState,
    EncoderState,
    EpochKdfChains,
    KdfChainState,
    SckaOutputKey,
    SckaReceiveResult,
    SckaSendResult,
    SpqrHeader,
    SpqrMessageType,
    SpqrRatchetState,
    SpqrSckaMessage,
)


PROTOCOL_INFO = b"SPQR_MLKEM1024_HMAC-SHA256"
MAC_SIZE = 32

HEADER_SIZE = 64
EK_SIZE = 1536
CT1_SIZE = 1408
CT2_SIZE = 160

SPQR_MAX_CHUNKS = 3
SPQR_LARGEST_CHUNKABLE_MESSAGE_SIZE = max(HEADER_SIZE + MAC_SIZE, EK_SIZE, CT1_SIZE, CT2_SIZE + MAC_SIZE)
SPQR_FIXED_CHUNK_SIZE = (SPQR_LARGEST_CHUNKABLE_MESSAGE_SIZE + SPQR_MAX_CHUNKS - 1) // SPQR_MAX_CHUNKS


def _to_bytes_epoch(epoch: int) -> bytes:
    return max(0, epoch).to_bytes(8, "big", signed=False)


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    okm = b""
    t = b""
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        okm += t
        counter += 1
    return okm[:length]


def _sha3(data: bytes) -> bytes:
    return hashlib.sha3_256(data).digest()


def _expand(seed: bytes, length: int) -> bytes:
    stream = b""
    block = 0
    while len(stream) < length:
        stream += hashlib.sha256(seed + block.to_bytes(4, "big")).digest()
        block += 1
    return stream[:length]


def _mac(mac_key: bytes, msg: bytes) -> bytes:
    return hmac.new(mac_key, msg, hashlib.sha256).digest()[:MAC_SIZE]


def _concat_bytes(*parts: bytes) -> bytes:
    return b"".join(parts)


def KDF_AUTH(root_key: bytes, update_key: bytes, epoch: int) -> tuple[bytes, bytes]:
    info = _concat_bytes(PROTOCOL_INFO, b":Authenticator Update", _to_bytes_epoch(epoch))
    prk = _hkdf_extract(root_key, update_key)
    output = _hkdf_expand(prk, info, 64)
    return output[:32], output[32:64]


def KDF_OK(shared_secret: bytes, epoch: int) -> bytes:
    info = _concat_bytes(PROTOCOL_INFO, b":SCKA Key", _to_bytes_epoch(epoch))
    prk = _hkdf_extract(b"\x00" * 32, shared_secret)
    return _hkdf_expand(prk, info, 32)


def KDF_SCKA_INIT(sk: bytes) -> tuple[bytes, bytes, bytes]:
    info = _concat_bytes(PROTOCOL_INFO, b":SCKA Init")
    prk = _hkdf_extract(b"\x00" * 32, sk)
    output = _hkdf_expand(prk, info, 96)
    return output[:32], output[32:64], output[64:96]


def KDF_SCKA_RK(rk: bytes, scka_output: bytes) -> tuple[bytes, bytes, bytes]:
    info = _concat_bytes(PROTOCOL_INFO, b":SCKA RK")
    prk = _hkdf_extract(rk, scka_output)
    output = _hkdf_expand(prk, info, 96)
    return output[:32], output[32:64], output[64:96]


def KDF_SCKA_CK(ck: bytes, ctr: int) -> tuple[bytes, bytes]:
    info = _concat_bytes(PROTOCOL_INFO, b":SCKA CK", _to_bytes_epoch(ctr))
    prk = _hkdf_extract(ck, _to_bytes_epoch(ctr))
    output = _hkdf_expand(prk, info, 64)
    return output[:32], output[32:64]


def KDFChain(ck: bytes) -> KdfChainState:
    return KdfChainState(CK=ck, N=0)


class Authenticator:
    @staticmethod
    def Init(epoch: int, key: bytes) -> AuthenticatorState:
        state = AuthenticatorState(root_key=b"\x00" * 32, mac_key=None)
        Authenticator.Update(state, epoch, key)
        return state

    @staticmethod
    def Update(auth_state: AuthenticatorState, epoch: int, key: bytes) -> None:
        auth_state.root_key, auth_state.mac_key = KDF_AUTH(auth_state.root_key, key, epoch)

    @staticmethod
    def MacHdr(auth_state: AuthenticatorState, epoch: int, hdr: bytes) -> bytes:
        if auth_state.mac_key is None:
            raise ValueError("Authenticator mac_key is not initialized")
        msg = _concat_bytes(PROTOCOL_INFO, b":ekheader", _to_bytes_epoch(epoch), hdr)
        return _mac(auth_state.mac_key, msg)

    @staticmethod
    def MacCt(auth_state: AuthenticatorState, epoch: int, ct: bytes) -> bytes:
        if auth_state.mac_key is None:
            raise ValueError("Authenticator mac_key is not initialized")
        msg = _concat_bytes(PROTOCOL_INFO, b":ciphertext", _to_bytes_epoch(epoch), ct)
        return _mac(auth_state.mac_key, msg)

    @staticmethod
    def VfyHdr(auth_state: AuthenticatorState, epoch: int, hdr: bytes, expected_mac: bytes) -> None:
        actual = Authenticator.MacHdr(auth_state, epoch, hdr)
        if not hmac.compare_digest(actual, expected_mac):
            raise ValueError("SPQR header MAC verification failed")

    @staticmethod
    def VfyCt(auth_state: AuthenticatorState, epoch: int, ct: bytes, expected_mac: bytes) -> None:
        actual = Authenticator.MacCt(auth_state, epoch, ct)
        if not hmac.compare_digest(actual, expected_mac):
            raise ValueError("SPQR ciphertext MAC verification failed")


class SimIncrementalKEM:
    @staticmethod
    def KeyGen() -> tuple[bytes, bytes, bytes]:
        return ext.SPQR_INCREMENTAL_KEM_KEYGEN()

    @staticmethod
    def Encaps1(ek_header: bytes) -> tuple[bytes, bytes, bytes]:
        return ext.SPQR_INCREMENTAL_KEM_ENCAPS1(ek_header)

    @staticmethod
    def Encaps2(encaps_secret: bytes, ek_header: bytes, ek_vector: bytes) -> bytes:
        return ext.SPQR_INCREMENTAL_KEM_ENCAPS2(encaps_secret, ek_header, ek_vector)

    @staticmethod
    def Decaps(dk: bytes, ct1: bytes, ct2: bytes) -> bytes:
        return ext.SPQR_INCREMENTAL_KEM_DECAPS(dk, ct1, ct2)


def Encode(byte_array: bytes) -> EncoderState:
    return EncoderState(message=byte_array, chunk_size=SPQR_FIXED_CHUNK_SIZE)


def Decoder_new(message_size: int) -> DecoderState:
    return DecoderState(message_size=message_size)


class SckaNode:
    epoch: int
    auth: AuthenticatorState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        raise NotImplementedError

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        raise NotImplementedError


@dataclass
class KeysUnsampled(SckaNode):
    epoch: int
    auth: AuthenticatorState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # Generate keypair and header
        dk, ek_header, ek_vector = SimIncrementalKEM.KeyGen()
        mac = Authenticator.MacHdr(self.auth, self.epoch, ek_header)
        header_encoder = Encode(_concat_bytes(ek_header, mac))
        # Generate message
        chunk = header_encoder.next_chunk()
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.HDR, data=chunk)

        # Update state
        # Transition (1)
        state.node = KeysSampled(
            epoch=self.epoch,
            auth=self.auth,
            dk=dk,
            ek_header=ek_header,
            ek_vector=ek_vector,
            header_encoder=header_encoder,
        )

        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class KeysSampled(SckaNode):
    epoch: int
    auth: AuthenticatorState
    dk: bytes
    ek_header: bytes
    ek_vector: bytes
    header_encoder: EncoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # Generate next header chunk
        chunk = self.header_encoder.next_chunk()
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.HDR, data=chunk)

        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        if msg.epoch == self.epoch and msg.msg_type == SpqrMessageType.CT1:
            # Initialize ct1 decoder and ek encoder
            ct1_decoder = Decoder_new(CT1_SIZE)
            ct1_decoder.add_chunk(msg.data)
            ek_encoder = Encode(self.ek_vector)

            # Update state
            # Transition (2)
            state.node = HeaderSent(
                epoch=self.epoch,
                auth=self.auth,
                dk=self.dk,
                ek_header=self.ek_header,
                ek_vector=self.ek_vector,
                ct1_decoder=ct1_decoder,
                ek_encoder=ek_encoder,
            )
        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class HeaderSent(SckaNode):
    epoch: int
    auth: AuthenticatorState
    dk: bytes
    ek_header: bytes
    ek_vector: bytes
    ct1_decoder: DecoderState
    ek_encoder: EncoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # Generate next ek_vector chunk
        chunk = self.ek_encoder.next_chunk()
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.EK, data=chunk)

        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        if msg.epoch == self.epoch and msg.msg_type == SpqrMessageType.CT1:
            # Add chunk to decoder
            self.ct1_decoder.add_chunk(msg.data)

            # Check if ct1 is complete
            if self.ct1_decoder.has_message():
                ct1 = self.ct1_decoder.message()

                # Update state
                # Transition (3)
                state.node = Ct1Received(
                    epoch=self.epoch,
                    auth=self.auth,
                    dk=self.dk,
                    ek_header=self.ek_header,
                    ek_vector=self.ek_vector,
                    ct1=ct1,
                    ek_encoder=self.ek_encoder,
                )
        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class Ct1Received(SckaNode):
    epoch: int
    auth: AuthenticatorState
    dk: bytes
    ek_header: bytes
    ek_vector: bytes
    ct1: bytes
    ek_encoder: EncoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # Generate next ek_vector chunk with acknowledgment
        chunk = self.ek_encoder.next_chunk()
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.EK_CT1_ACK, data=chunk)

        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        if msg.epoch == self.epoch and msg.msg_type == SpqrMessageType.CT2:
            # Initialize ct2 decoder
            ct2_decoder = Decoder_new(CT2_SIZE + MAC_SIZE)
            ct2_decoder.add_chunk(msg.data)

            # Update state
            # Transition (4)
            state.node = EkSentCt1Received(
                epoch=self.epoch,
                auth=self.auth,
                dk=self.dk,
                ek_header=self.ek_header,
                ek_vector=self.ek_vector,
                ct1=self.ct1,
                ct2_decoder=ct2_decoder,
            )
        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class EkSentCt1Received(SckaNode):
    epoch: int
    auth: AuthenticatorState
    dk: bytes
    ek_header: bytes
    ek_vector: bytes
    ct1: bytes
    ct2_decoder: DecoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # No data to send
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.NONE)
        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        if msg.epoch == self.epoch and msg.msg_type == SpqrMessageType.CT2:
            # Add chunk to decoder
            self.ct2_decoder.add_chunk(msg.data)

            # Check if ct2 is complete
            if self.ct2_decoder.has_message():
                ct2_with_mac = self.ct2_decoder.message() or b""
                ct2 = ct2_with_mac[:CT2_SIZE]
                mac = ct2_with_mac[CT2_SIZE:]

                # Decapsulate shared secret using the incremental KEM interface
                ss = SimIncrementalKEM.Decaps(self.dk, self.ct1, ct2)
                ss = KDF_OK(ss, self.epoch)

                # Update authenticator and verify MAC
                Authenticator.Update(self.auth, self.epoch, ss)
                Authenticator.VfyCt(self.auth, self.epoch, _concat_bytes(self.ct1, ct2), mac)

                # Prepare for next epoch
                header_decoder = Decoder_new(HEADER_SIZE + MAC_SIZE)

                # Update state and return key
                # Transition (5)
                state.node = NoHeaderReceived(
                    epoch=self.epoch + 1,
                    auth=self.auth,
                    header_decoder=header_decoder,
                )
                return SckaReceiveResult(
                    receiving_epoch=self.epoch - 1,
                    output_key=SckaOutputKey(epoch=self.epoch, key=ss),
                )
        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class NoHeaderReceived(SckaNode):
    epoch: int
    auth: AuthenticatorState
    header_decoder: DecoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # No data to send
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.NONE)
        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        if msg.epoch == self.epoch and msg.msg_type == SpqrMessageType.HDR:
            # Add chunk to decoder
            self.header_decoder.add_chunk(msg.data)

            # Check if header is complete
            if self.header_decoder.has_message():
                header_with_mac = self.header_decoder.message() or b""
                ek_header = header_with_mac[:HEADER_SIZE]
                mac = header_with_mac[HEADER_SIZE:]

                # Verify header MAC
                Authenticator.VfyHdr(self.auth, self.epoch, ek_header, mac)

                # Prepare ek_vector decoder
                ek_decoder = Decoder_new(EK_SIZE)

                # Update state
                # Transition (6)
                state.node = HeaderReceived(
                    epoch=self.epoch,
                    auth=self.auth,
                    ek_header=ek_header,
                    ek_decoder=ek_decoder,
                )
        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class HeaderReceived(SckaNode):
    epoch: int
    auth: AuthenticatorState
    ek_header: bytes
    ek_decoder: DecoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # Generate shared secret and ct1 using incremental KEM interface
        encaps_secret, ct1, ss = SimIncrementalKEM.Encaps1(self.ek_header)
        ss = KDF_OK(ss, self.epoch)

        # Update authenticator
        Authenticator.Update(self.auth, self.epoch, ss)

        # Encode ct1 for transmission
        ct1_encoder = Encode(ct1)
        chunk = ct1_encoder.next_chunk()

        # Update state
        # Transition (7)
        state.node = Ct1Sampled(
            epoch=self.epoch,
            auth=self.auth,
            ek_header=self.ek_header,
            encaps_secret=encaps_secret,
            ct1=ct1,
            ct1_encoder=ct1_encoder,
            ek_decoder=self.ek_decoder,
        )
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.CT1, data=chunk)
        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=SckaOutputKey(epoch=self.epoch, key=ss))

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        # No action taken
        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class Ct1Sampled(SckaNode):
    epoch: int
    auth: AuthenticatorState
    ek_header: bytes
    encaps_secret: bytes
    ct1: bytes
    ct1_encoder: EncoderState
    ek_decoder: DecoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # Generate next ct1 chunk
        chunk = self.ct1_encoder.next_chunk()
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.CT1, data=chunk)

        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        if msg.epoch == self.epoch and msg.msg_type == SpqrMessageType.EK:
            # Add ek_vector chunk
            self.ek_decoder.add_chunk(msg.data)

            # Check if ek_vector is complete
            if self.ek_decoder.has_message():
                ek_vector = self.ek_decoder.message() or b""

                # Verify ek_vector integrity using ek_header
                ek_seed = self.ek_header[:32]
                hek = self.ek_header[32:64]
                if _sha3(_concat_bytes(ek_seed, ek_vector)) != hek:
                    raise ValueError("EK integrity check failed")

                # Update state
                # Transition (10)
                state.node = EkReceivedCt1Sampled(
                    epoch=self.epoch,
                    auth=self.auth,
                    encaps_secret=self.encaps_secret,
                    ct1=self.ct1,
                    ek_header=self.ek_header,
                    ek_vector=ek_vector,
                    ct1_encoder=self.ct1_encoder,
                )
            return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)

        if msg.epoch == self.epoch and msg.msg_type == SpqrMessageType.EK_CT1_ACK:
            # Add ek_vector chunk (with acknowledgment)
            self.ek_decoder.add_chunk(msg.data)

            # Check if ek_vector is complete
            if self.ek_decoder.has_message():
                ek_vector = self.ek_decoder.message()

                # Verify ek_vector integrity using ek_header
                ek_seed = self.ek_header[:32]
                hek = self.ek_header[32:64]
                if _sha3(_concat_bytes(ek_seed, ek_vector)) != hek:
                    raise ValueError("EK integrity check failed")

                # Complete encapsulation using incremental KEM interface
                ct2 = SimIncrementalKEM.Encaps2(self.encaps_secret, self.ek_header, ek_vector)
                mac = Authenticator.MacCt(self.auth, self.epoch, _concat_bytes(self.ct1, ct2))
                ct2_encoder = Encode(_concat_bytes(ct2, mac))

                # Update state
                # Transition (9)
                state.node = Ct2Sampled(
                    epoch=self.epoch,
                    auth=self.auth,
                    ct2_encoder=ct2_encoder
                )
            else:
                # Update state
                # Transition (8)
                state.node = Ct1Acknowledged(
                    epoch=self.epoch,
                    auth=self.auth,
                    encaps_secret=self.encaps_secret,
                    ek_header=self.ek_header,
                    ct1=self.ct1,
                    ek_decoder=self.ek_decoder,
                )

        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class EkReceivedCt1Sampled(SckaNode):
    epoch: int
    auth: AuthenticatorState
    encaps_secret: bytes
    ct1: bytes
    ek_header: bytes
    ek_vector: bytes
    ct1_encoder: EncoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # Generate next ct1 chunk
        chunk = self.ct1_encoder.next_chunk()
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.CT1, data=chunk)

        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        if msg.epoch == self.epoch and msg.msg_type == SpqrMessageType.EK_CT1_ACK:
            # Complete encapsulation using incremental KEM interface
            ct2 = SimIncrementalKEM.Encaps2(self.encaps_secret, self.ek_header, self.ek_vector)
            mac = Authenticator.MacCt(self.auth, self.epoch, _concat_bytes(self.ct1, ct2))
            ct2_encoder = Encode(_concat_bytes(ct2, mac))

            # Update state
            # Transition (12)
            state.node = Ct2Sampled(
                epoch=self.epoch,
                auth=self.auth,
                ct2_encoder=ct2_encoder
            )
        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class Ct1Acknowledged(SckaNode):
    epoch: int
    auth: AuthenticatorState
    encaps_secret: bytes
    ek_header: bytes
    ct1: bytes
    ek_decoder: DecoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # No data to send
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.NONE)

        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        if msg.epoch == self.epoch and msg.msg_type == SpqrMessageType.EK_CT1_ACK:
            # Add ek_vector chunk
            self.ek_decoder.add_chunk(msg.data)

            # Check if ek_vector is complete
            if self.ek_decoder.has_message():
                ek_vector = self.ek_decoder.message() or b""

                # Verify ek_vector integrity using ek_header
                ek_seed = self.ek_header[:32]
                hek = self.ek_header[32:64]
                if _sha3(_concat_bytes(ek_seed, ek_vector)) != hek:
                    raise ValueError("EK integrity check failed")

                # Complete encapsulation using incremental KEM interface
                ct2 = SimIncrementalKEM.Encaps2(self.encaps_secret, self.ek_header, ek_vector)
                mac = Authenticator.MacCt(self.auth, self.epoch, _concat_bytes(self.ct1, ct2))
                ct2_encoder = Encode(_concat_bytes(ct2, mac))

                # Update state
                # Transition (11)
                state.node = Ct2Sampled(
                    epoch=self.epoch,
                    auth=self.auth,
                    ct2_encoder=ct2_encoder
                )
        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


@dataclass
class Ct2Sampled(SckaNode):
    epoch: int
    auth: AuthenticatorState
    ct2_encoder: EncoderState

    def send(self, state: BraidProtocolState) -> SckaSendResult:
        # Generate next ct2 chunk
        chunk = self.ct2_encoder.next_chunk()
        msg = SpqrSckaMessage(epoch=self.epoch, msg_type=SpqrMessageType.CT2, data=chunk)

        return SckaSendResult(msg=msg, sending_epoch=self.epoch - 1, output_key=None)

    def receive(self, state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
        if msg.epoch == self.epoch + 1:
            # Next epoch has begun
            # Transition (13)
            state.node = KeysUnsampled(epoch=self.epoch + 1, auth=self.auth)
            return SckaReceiveResult(receiving_epoch=self.epoch, output_key=None)

        return SckaReceiveResult(receiving_epoch=self.epoch - 1, output_key=None)


def InitAlice(shared_secret: bytes) -> BraidProtocolState:
    epoch = 1
    auth = Authenticator.Init(epoch, shared_secret)
    return BraidProtocolState(node=KeysUnsampled(epoch=epoch, auth=auth))


def InitBob(shared_secret: bytes) -> BraidProtocolState:
    epoch = 1
    auth = Authenticator.Init(epoch, shared_secret)
    header_decoder = Decoder_new(HEADER_SIZE + MAC_SIZE)
    return BraidProtocolState(node=NoHeaderReceived(epoch=epoch, auth=auth, header_decoder=header_decoder))


def _require_scka_node(node: object) -> SckaNode:
    if isinstance(node, SckaNode):
        return node
    raise ValueError("Invalid SCKA state node")


def SCKASend(state: BraidProtocolState) -> SckaSendResult:
    node = _require_scka_node(state.node)
    return node.send(state)


def SCKAReceive(state: BraidProtocolState, msg: SpqrSckaMessage) -> SckaReceiveResult:
    node = _require_scka_node(state.node)
    return node.receive(state, msg)


def SCKAInitAlice(sk: bytes) -> BraidProtocolState:
    return InitAlice(sk)


def SCKAInitBob(sk: bytes) -> BraidProtocolState:
    return InitBob(sk)


def RatchetInitAliceSCKA(sk: bytes) -> SpqrRatchetState:
    scka_state = SCKAInitAlice(sk)
    rk, cks, ckr = KDF_SCKA_INIT(sk)
    return SpqrRatchetState(
        RK=rk,
        epoch=0,
        kdfchains={0: EpochKdfChains(send=KDFChain(cks), receive=KDFChain(ckr))},
        MKSKIPPED={},
        direction="A2B",
        scka_state=scka_state,
    )


def RatchetInitBobSCKA(sk: bytes) -> SpqrRatchetState:
    scka_state = SCKAInitBob(sk)
    rk, ckr, cks = KDF_SCKA_INIT(sk)
    return SpqrRatchetState(
        RK=rk,
        epoch=0,
        kdfchains={0: EpochKdfChains(send=KDFChain(cks), receive=KDFChain(ckr))},
        MKSKIPPED={},
        direction="B2A",
        scka_state=scka_state,
    )


def ClearOldEpochs(state: SpqrRatchetState, sending_epoch: int) -> None:
    old_epoch = sending_epoch - 2
    if old_epoch in state.kdfchains:
        del state.kdfchains[old_epoch]
    if old_epoch in state.MKSKIPPED:
        del state.MKSKIPPED[old_epoch]


def TrySkippedMessageKeys(state: SpqrRatchetState, key_epoch: int, n: int) -> bytes | None:
    epoch_skipped = state.MKSKIPPED.get(key_epoch)
    if not epoch_skipped or n not in epoch_skipped:
        return None
    mk = epoch_skipped.pop(n)
    if not epoch_skipped:
        del state.MKSKIPPED[key_epoch]
    return mk


def SkipMessageKeys(state: SpqrRatchetState, epoch: int, until: int, max_skip: int = 50) -> None:
    chains = state.kdfchains.get(epoch)
    if chains is None or chains.receive is None:
        return
    if chains.receive.N + max_skip < until:
        raise ValueError("Too many skipped SPQR message keys")

    while chains.receive.N < until:
        chains.receive.N += 1
        chains.receive.CK, mk = KDF_SCKA_CK(chains.receive.CK, chains.receive.N)
        state.MKSKIPPED.setdefault(epoch, {})[chains.receive.N] = mk


def SCKARatchetSendKey(state: SpqrRatchetState) -> tuple[SpqrSckaMessage, int, bytes, dict[str, Any]]:
    if state.scka_state is None:
        raise ValueError("SPQR state has no SCKA state")

    send_result = SCKASend(state.scka_state)
    rk_before = state.RK
    derived_output_key = send_result.output_key.key if send_result.output_key is not None else None
    new_cks = None
    new_ckr = None
    if send_result.output_key is not None:
        key_epoch = send_result.output_key.epoch
        key = send_result.output_key.key
        if state.epoch + 1 != key_epoch:
            raise ValueError("Unexpected SPQR key epoch during send")

        state.RK, cks, ckr = KDF_SCKA_RK(state.RK, key)
        if state.direction == "B2A":
            cks, ckr = ckr, cks
        new_cks = cks
        new_ckr = ckr

        state.kdfchains[key_epoch] = EpochKdfChains(send=KDFChain(cks), receive=KDFChain(ckr))
        state.epoch = key_epoch
        ClearOldEpochs(state, send_result.sending_epoch)

    prev_epoch = send_result.sending_epoch - 1
    prev_chains = state.kdfchains.get(prev_epoch)
    if prev_chains is not None:
        prev_chains.send = None

    chains = state.kdfchains.get(send_result.sending_epoch)
    if chains is None or chains.send is None:
        raise ValueError("Missing sender chain for sending_epoch")

    chain_key_before = chains.send.CK
    chains.send.N += 1
    counter = chains.send.N
    chains.send.CK, mk = KDF_SCKA_CK(chains.send.CK, counter)

    trace = {
        "sending_epoch": send_result.sending_epoch,
        "counter": counter,
        "chain_key_before": chain_key_before,
        "chain_key_after": chains.send.CK,
        "mk": mk,
        "rk_before": rk_before,
        "rk_after": state.RK,
        "new_cks": new_cks,
        "new_ckr": new_ckr,
        "scka_output_key": derived_output_key,
    }
    return send_result.msg, counter, mk, trace


def _serialize_header_for_ad(header: SpqrHeader) -> bytes:
    payload = {
        "msg": header.msg.to_dict(),
        "n": header.n,
    }
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _concat_ad_header(ad: bytes, header: SpqrHeader) -> bytes:
    ad = ad or b""
    header_bytes = _serialize_header_for_ad(header)
    return len(ad).to_bytes(4, "big") + ad + header_bytes


def SCKARatchetEncrypt(
    state: SpqrRatchetState,
    plaintext: bytes,
    AD: bytes,
) -> tuple[SpqrHeader, bytes, dict[str, Any]]:
    msg, n, mk, key_trace = SCKARatchetSendKey(state)
    header = SpqrHeader(msg=msg, n=n)
    ad_header = _concat_ad_header(AD, header)
    ciphertext = ext.ENCRYPT(mk, plaintext, ad_header)
    trace = {
        **key_trace,
        "mk": mk,
        "header": header,
        "ad_header": ad_header,
        "plaintext": plaintext,
        "ciphertext": ciphertext,
    }
    return header, ciphertext, trace


def SCKARatchetReceiveKey(state: SpqrRatchetState, header: SpqrHeader) -> tuple[bytes, dict[str, Any]]:
    if state.scka_state is None:
        raise ValueError("SPQR state has no SCKA state")

    receive_result = SCKAReceive(state.scka_state, header.msg)
    rk_before = state.RK
    derived_output_key = receive_result.output_key.key if receive_result.output_key is not None else None
    new_cks = None
    new_ckr = None

    if receive_result.output_key is not None:
        key_epoch = receive_result.output_key.epoch
        key = receive_result.output_key.key
        if state.epoch + 1 != key_epoch:
            raise ValueError("Unexpected SPQR key epoch during receive")

        state.RK, cks, ckr = KDF_SCKA_RK(state.RK, key)
        if state.direction == "B2A":
            cks, ckr = ckr, cks
        new_cks = cks
        new_ckr = ckr

        state.kdfchains[key_epoch] = EpochKdfChains(send=KDFChain(cks), receive=KDFChain(ckr))
        state.epoch = key_epoch

    receiving_epoch = receive_result.receiving_epoch
    mk = TrySkippedMessageKeys(state, receiving_epoch, header.n)
    if mk is not None:
        trace = {
            "receiving_epoch": receiving_epoch,
            "counter": header.n,
            "chain_key_before": None,
            "chain_key_after": None,
            "mk": mk,
            "rk_before": rk_before,
            "rk_after": state.RK,
            "new_cks": new_cks,
            "new_ckr": new_ckr,
            "scka_output_key": derived_output_key,
            "used_skipped_key": True,
        }
        return mk, trace

    SkipMessageKeys(state, receiving_epoch, max(0, header.n - 1))

    chains = state.kdfchains.get(receiving_epoch)
    if chains is None or chains.receive is None:
        raise ValueError("Missing receiver chain for receiving_epoch")

    chain_key_before = chains.receive.CK
    chains.receive.N += 1
    counter = chains.receive.N
    chains.receive.CK, mk = KDF_SCKA_CK(chains.receive.CK, counter)

    trace = {
        "receiving_epoch": receiving_epoch,
        "counter": counter,
        "chain_key_before": chain_key_before,
        "chain_key_after": chains.receive.CK,
        "mk": mk,
        "rk_before": rk_before,
        "rk_after": state.RK,
        "new_cks": new_cks,
        "new_ckr": new_ckr,
        "scka_output_key": derived_output_key,
        "used_skipped_key": False,
    }
    return mk, trace


def SCKARatchetDecrypt(
    state: SpqrRatchetState,
    header: SpqrHeader,
    ciphertext: bytes,
    AD: bytes,
) -> tuple[bytes, dict[str, Any]]:
    mk, key_trace = SCKARatchetReceiveKey(state, header)
    ad_header = _concat_ad_header(AD, header)
    plaintext = ext.DECRYPT(mk, ciphertext, ad_header)
    trace = {
        **key_trace,
        "mk": mk,
        "header": header,
        "ad_header": ad_header,
        "ciphertext": ciphertext,
        "decrypted": plaintext,
    }
    return plaintext, trace
