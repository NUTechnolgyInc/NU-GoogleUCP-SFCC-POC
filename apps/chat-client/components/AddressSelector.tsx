/*
 * Copyright 2026 UCP Authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { useState } from 'react';
import type { CustomerAddress } from '../types';

interface AddressSelectorProps {
    addresses: CustomerAddress[];
    onSelectAddress: (addressId: string) => void;
}

function AddressSelector({ addresses, onSelectAddress }: AddressSelectorProps) {
    const [selectedId, setSelectedId] = useState<string | null>(null);

    const handleSelect = (addressId: string) => {
        setSelectedId(addressId);
    };

    const handleConfirm = () => {
        if (selectedId) {
            onSelectAddress(selectedId);
        }
    };

    return (
        <div className="my-2 p-4 bg-white border border-gray-200 rounded-xl shadow-sm max-w-md">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">
                Select a delivery address:
            </h3>
            <div className="space-y-2">
                {addresses.map((addr) => (
                    <label
                        key={addr.addressId}
                        className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all ${selectedId === addr.addressId
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                            }`}
                    >
                        <input
                            type="radio"
                            name="customer-address"
                            value={addr.addressId}
                            checked={selectedId === addr.addressId}
                            onChange={() => handleSelect(addr.addressId)}
                            className="mt-1 accent-blue-500"
                        />
                        <div className="flex-1 min-w-0">
                            <div className="font-medium text-gray-800 text-sm">
                                {addr.addressId}
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5">
                                {addr.firstName} {addr.lastName}
                            </div>
                            <div className="text-xs text-gray-500">
                                {addr.address1}
                                {addr.address2 ? `, ${addr.address2}` : ''}
                            </div>
                            <div className="text-xs text-gray-500">
                                {addr.city}, {addr.stateCode} {addr.postalCode}{' '}
                                {addr.countryCode}
                            </div>
                            {addr.phone && (
                                <div className="text-xs text-gray-400 mt-0.5">
                                    📞 {addr.phone}
                                </div>
                            )}
                        </div>
                    </label>
                ))}
            </div>
            <button
                type="button"
                onClick={handleConfirm}
                disabled={!selectedId}
                className={`mt-3 w-full py-2 px-4 rounded-lg text-sm font-medium transition-all ${selectedId
                        ? 'bg-blue-500 text-white hover:bg-blue-600 shadow-sm'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
            >
                Use this address
            </button>
        </div>
    );
}

export default AddressSelector;
