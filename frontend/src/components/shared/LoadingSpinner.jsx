import { motion } from 'framer-motion'

export default function LoadingSpinner() {
  return (
    <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0.3, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{
            duration: 0.6,
            repeat: Infinity,
            repeatType: 'reverse',
            delay: i * 0.2,
          }}
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: 'var(--cyan)',
            boxShadow: '0 0 8px var(--cyan)',
          }}
        />
      ))}
    </div>
  )
}
