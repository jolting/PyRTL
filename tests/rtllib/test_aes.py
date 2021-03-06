import unittest

import pyrtl
import pyrtl.corecircuits
from pyrtl.rtllib import aes, testingutils


class TestAES(unittest.TestCase):
    """
    Test vectors are retrieved from:
    http://csrc.nist.gov/publications/fips/fips197/fips-197.pdf
    """

    def setUp(self):
        pyrtl.reset_working_block()
        self.aes = aes.AES()
        self.in_vector = pyrtl.Input(bitwidth=128, name='in_vector')
        self.out_vector = pyrtl.Output(bitwidth=128, name='out_vector')

    def test_inv_shift_rows(self):
        self.out_vector <<= self.aes.inv_shift_rows(self.in_vector)

        in_vals = [0x3e1c22c0b6fcbf768da85067f6170495, 0x2d6d7ef03f33e334093602dd5bfb12c7]
        true_result = [0x3e175076b61c04678dfc2295f6a8bfc0, 0x2dfb02343f6d12dd09337ec75b36e3f0]
        calculated_result = testingutils.sim_and_ret_out(self.out_vector, (self.in_vector,), (in_vals,))
        self.assertEqual(calculated_result, true_result)

    def test_inv_sub_bytes(self):
        self.out_vector <<= self.aes.inv_sub_bytes(self.in_vector)

        in_vals = [0x3e175076b61c04678dfc2295f6a8bfc0, 0x2dfb02343f6d12dd09337ec75b36e3f0]
        true_result = [0xd1876c0f79c4300ab45594add66ff41f, 0xfa636a2825b339c940668a3157244d17]
        calculated_result = testingutils.sim_and_ret_out(self.out_vector, (self.in_vector,), (in_vals,))
        self.assertEqual(calculated_result, true_result)

    def test_inv_mix_columns(self):
        self.out_vector <<= self.aes.inv_mix_columns(self.in_vector)

        in_vals = [0xe9f74eec023020f61bf2ccf2353c21c7, 0xbaa03de7a1f9b56ed5512cba5f414d23]
        real_res = [0x54d990a16ba09ab596bbf40ea111702f, 0x3e1c22c0b6fcbf768da85067f6170495]
        calculated_result = testingutils.sim_and_ret_out(self.out_vector, (self.in_vector,), (in_vals,))
        self.assertEqual(calculated_result, real_res)

    @unittest.skip
    def test_key_expansion(self):
        # This is not at all correct. Needs to be completely rewritten
        self.out_vector <<= pyrtl.corecircuits.concat_list(self.aes.decryption_key_gen(self.in_vector))

        in_vals = [0xd1876c0f79c4300ab45594add66ff41f, 0xfa636a2825b339c940668a3157244d17]
        true_result = [0x3e175076b61c04678dfc2295f6a8bfc0, 0x2dfb02343f6d12dd09337ec75b36e3f0]
        calculated_result = testingutils.sim_and_ret_out(self.out_vector, (self.in_vector,), (in_vals,))
        self.assertEqual(calculated_result, true_result)

    def test_aes_full(self):
        aes_key = pyrtl.Input(bitwidth=128, name='aes_key')
        self.out_vector <<= self.aes.decryption(self.in_vector, aes_key)

        ciphers = [0x3ad77bb40d7a3660a89ecaf32466ef97, 0x66e94bd4ef8a2c3b884cfa59ca342b2e]
        keys = [0x2b7e151628aed2a6abf7158809cf4f3c, 0x0]
        plain_text = [0x6bc1bee22e409f96e93d7e117393172a, 0x0]
        calculated_result = testingutils.sim_and_ret_out(self.out_vector, (self.in_vector, aes_key),
                                                    (ciphers, keys))
        self.assertEqual(calculated_result, plain_text)

    def test_aes_state_machine(self):
        # self.longMessage = True

        aes_key = pyrtl.Input(bitwidth=128, name='aes_key')
        reset = pyrtl.Input(1)
        ready = pyrtl.Output(1, name='ready')

        decrypt_ready, decrypt_out = self.aes.decryption_statem(self.in_vector, aes_key, reset)
        self.out_vector <<= decrypt_out
        ready <<= decrypt_ready

        sim_trace = pyrtl.SimulationTrace()
        sim = pyrtl.Simulation(tracer=sim_trace)

        sim.step({
            self.in_vector: 0x69c4e0d86a7b0430d8cdb78070b4c55a,
            aes_key: 0x000102030405060708090a0b0c0d0e0f,
            reset: 1
        })

        true_vals = [0x69c4e0d86a7b0430d8cdb78070b4c55a, 0x7ad5fda789ef4e272bca100b3d9ff59f,
                     0x54d990a16ba09ab596bbf40ea111702f, 0x3e1c22c0b6fcbf768da85067f6170495,
                     0xb458124c68b68a014b99f82e5f15554c, 0xe8dab6901477d4653ff7f5e2e747dd4f,
                     0x36339d50f9b539269f2c092dc4406d23, 0x2d6d7ef03f33e334093602dd5bfb12c7,
                     0x3bd92268fc74fb735767cbe0c0590e2d, 0xa7be1a6997ad739bd8c9ca451f618b61,
                     0x6353e08c0960e104cd70b751bacad0e7, 0x00112233445566778899aabbccddeeff,
                     0x00112233445566778899aabbccddeeff,]

        for cycle in range(1, 13):  # Bogus data for while the state machine churns
            sim.step({
                self.in_vector: 0x0, aes_key: 0x1, reset: 0
            })
            circuit_out = sim_trace.trace[self.out_vector][cycle]
            self.assertEqual(circuit_out, true_vals[cycle], "\nAssertion failed on cycle: " +
                             str(cycle) + " Gotten value: " + hex(circuit_out))

        for ready_signal in sim_trace.trace[ready][:11]:
            self.assertEquals(ready_signal, 0)

        for ready_signal in sim_trace.trace[ready][11:]:
            self.assertEquals(ready_signal, 1)
