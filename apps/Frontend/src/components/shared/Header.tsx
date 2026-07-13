import React from 'react';
import Image from 'next/image';
import { Button } from '../ui/button';
import { navItems } from '@/constants';
import Link from 'next/link';

const Header = () => {
  return (
    <header className='fixed top-0 right-0 left-0  flex justify-center items-center w-full h-[65px] mt-3 px-5 z-50'>
        <div className='flex justify-between items-center w-full max-w-[950px] h-full rounded-[20px] backdrop-blur-xl bg-black/40 px-4 md:px-6'>
            <div className='flex-shrink-0'>
                <Image src="/icons/logo.svg" alt="Learner Logo" width={109} height={28} />
            </div>
            
            <nav className='hidden lg:flex flex-1 max-w-[350px] mx-4'>
                <ul className='flex justify-between items-center w-full gap-2 md:gap-4'>
                    {navItems.map((item) => (
                        <li key={item.id}>
                            <Link href={item.url} className='text-text-secondary text-[14px] hover:text-text-primary transition-colors duration-200 whitespace-nowrap'>{item.title}</Link>
                        </li>
                    ))}
                </ul>
            </nav>

            <div className='flex justify-end gap-2 flex-shrink-0 items-center'>
                <Button variant="ghost" asChild>
                    <Link href="/auth/login" className='text-button text-text-secondary hover:text-text-primary'>Log in</Link>
                </Button>
                <Button variant="purple" asChild>
                    <Link href="/auth/signup" className='text-button'>Sign up</Link>
                </Button>
            </div>
        </div>
    </header>
  )
}

export default Header